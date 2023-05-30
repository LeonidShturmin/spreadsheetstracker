# import logging
import re

import gspread
from gspread.utils import column_letter_to_index
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from typing import Union, Tuple
import numpy as np

from config import tg_token
from logger import log_error, log_debug

SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SPREADSHEET_NAME = 'testsheet'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def speardsheets_connection_check(account_file: str, scopes: list, spreadsheet_name: str,
                                  sheet_number: int) -> Union[Tuple[
                                      bool, gspread.worksheet.Worksheet], None]:
    """
    checking a connection with Google Sheets API
    :param account_file: Path to credentials file
    :param spreadsheet_name: Name of spreadseets
    :param scopes: Rights of success
    :return: A tuple containing the join flag and the table sheet object, or None on error
    :sheet_number: Number of sheet 
    """
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            account_file, scopes=scopes)
        file = gspread.authorize(creds)

        workbook = file.open(spreadsheet_name)
        sheets = workbook.get_worksheet(sheet_number - 1)
        return True, sheets

    except GoogleAuthError as ex:
        log_error(f'Error {ex}')
        return False, None

    except HttpError as ex:
        log_error(f'Error {ex}')
        return False, None

    except gspread.exceptions.GSpreadException as ex:
        log_error(f'Error {ex.__class__.__name__}')
        return False, None

    except TimeoutError as ex:
        log_error(f'Error {ex}')
        return False, None

    except ConnectionError as ex:
        log_error(f'Error {ex}')
        return False, None

    except ValueError as ex:
        log_error(f'Error {ex}')
        return False, None

    except Exception as ex:
        log_error(f'Error {ex.__class__.__name__}')
        return False, None


def converting_of_number(column: int) -> str:
    """
    the function takes as input the column number (str)
    and returns its letter match in the spreadsheet
    for example column number 27 is AA in the google spreadsheet
    """
    if column // 26 == 0:
        column = ALPHABET[column - 1]
    else:
        column = ALPHABET[column // 26 - 1] + ALPHABET[column % 26 - 1]

    return column


def search_ranges(sheets: gspread.worksheet.Worksheet, start_coords: dict = None) -> tuple[dict, list]:
    """
    the function looks for a range of cells in a spreadsheet with values.
    Returns the coordinates of a range and a list of values in that range  
    """
    user_coordinates = {"leftcol": 'A', "leftrow": 1,
                        "rightcol": 'A', "rightrow":  1}
    all_values = []
    try:
        if start_coords is None or start_coords == 'dynamic':

            all_values = sheets.get_all_values()
            number_of_columns = len(all_values[0])

            user_coordinates['rightrow'] = len(all_values)
            user_coordinates['rightcol'] = converting_of_number(
                number_of_columns)

        else:
            values = sheets.range(start_coords)

            find_value = r"'([^']*)'"
            letters = re.findall("[A-Z]+", start_coords)
            numbers = re.findall(r"\d+", start_coords)

            user_coordinates["leftcol"] = letters[0]
            user_coordinates["rightcol"] = letters[1]
            user_coordinates["leftrow"] = int(numbers[0])
            user_coordinates["rightrow"] = int(numbers[1])

            column_index = column_letter_to_index(user_coordinates["rightcol"])

            values = [re.findall(find_value, str(cell))[0] for cell in values]
            all_values = []

            all_values = [[values[i], values[i+1]]
                          for i in range(0, len(values), column_index)]

    except gspread.exceptions.APIError:
        return None, None

    return user_coordinates, all_values


def compare_of_ranges(range_data: list) -> tuple[str, str]:
    """
    the function compares the range size. If the range has changed,
    the number of added rows and columns is returned

    :range_data: two-dimensional array with data from a table at 2 points in time
    """
    range_data_1 = np.array(range_data[0])
    range_data_2 = np.array(range_data[1])
    
    if len(range_data_1) != len(range_data_2) or len(range_data_1[0]) != len(range_data_2[0]):
        return False
    else:
        return True

def compare_of_values(data: list) -> tuple[bool, list[str]]:
    """
    function to compare values in a table at two points in time

    :param data: A tuple of two lists of lists of strings.
    :return: Tuple of flag and dictionary with changes.
    """
    flag = np.array_equal(data[0], data[1])
    changes = []
    if not flag:
        for row_index, (row1, row2) in enumerate(zip(data[0], data[1])):
            if row1 != row2:
                for col_index, (cell1, cell2) in enumerate(zip(row1, row2)):
                    if cell1 != cell2:
                        name_col = converting_of_number(col_index+1)
                        info = f'{name_col}{row_index+1}: {cell1} -> {cell2}'
                        changes.append(info)
        flag = False
        return flag, changes
    return flag, changes

