import re

import gspread
from typing import Optional
from gspread.utils import column_letter_to_index
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from typing import Union, Tuple
import numpy as np

from logger import log_error

ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

async def speardsheets_connection_check(account_file: str, scopes: list, spreadsheet_name: str,
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

    except (GoogleAuthError, HttpError, gspread.exceptions.GSpreadException, TimeoutError, ConnectionError, ValueError) as ex:
        log_error(f'Response from speardsheets_connection_check {ex.__class__.__name__}')
        return False, None
    except Exception as ex:

        log_error(f'Response from speardsheets_connection_check {ex.__class__.__name__}')
        return False, None

async def converting_of_number(column: int) -> Optional[str]:
    """
    the function takes as input the column number (str)
    and returns its letter match in the spreadsheet
    for example column number 27 is AA in the google spreadsheet
    """
    try:
        if column // 26 == 0:
            column = ALPHABET[column - 1]
        else:
            column = ALPHABET[column // 26 - 1] + ALPHABET[column % 26 - 1]
        return column
    
    except Exception as ex:
        log_error(f'Response from converting_of_number: {ex}')
        return None,

async def search_ranges(sheets: gspread.worksheet.Worksheet, start_coords: dict = None) -> Optional[tuple[dict, list]]:
    """
    the function looks for a range of cells in a spreadsheet with values.
    Returns the coordinates of a range and a list of values in that range  
    """
    user_coordinates = {"leftcol": 'A', "leftrow": 1,
                        "rightcol": 'A', "rightrow":  1}
    pattern = r"^[A-Z]+[0-9]+:[A-Z]+[0-9]+$"
    all_values = []
    try:
        if start_coords is None or start_coords == 'dynamic':
            all_values = sheets.get_all_values()
            number_of_columns = len(all_values[0])

            user_coordinates['rightrow'] = len(all_values)
            user_coordinates['rightcol'] = await converting_of_number(
                number_of_columns)

        else:
            match = re.match(pattern, start_coords)
            if match is None:
                return False, False
            values = sheets.range(start_coords)

            find_value = r"'([^']*)'"
            letters = re.findall("[A-Z]+", start_coords)
            numbers = re.findall(r"\d+", start_coords)

            user_coordinates["leftcol"] = letters[0]
            user_coordinates["rightcol"] = letters[1]
            user_coordinates["leftrow"] = int(numbers[0])
            user_coordinates["rightrow"] = int(numbers[1])

            column_index = column_letter_to_index(user_coordinates["rightcol"])

            cols = column_index
            rows = len(values)/column_index
            values = [re.findall(find_value, str(cell))[0] for cell in values]

            all_values = np.reshape(values, (int(rows), int(cols))).tolist()

    except gspread.exceptions.APIError as ex:
        log_error(f'Response from search_ranges: gspread.exceptions.APIError: {ex}')
        return None, None
    
    except TypeError as ex:
        log_error(f'Response from search_ranges: TypeError: {ex}')
        return None, None
    
    return user_coordinates, all_values


async def compare_of_ranges(range_data: list) -> Optional[bool]:
    """
    the function compares the range size. If the range has changed,
    the number of added rows and columns is returned

    :range_data: two-dimensional array with data from a table at 2 points in time
    """
    try:
        range_data_1 = np.array(range_data[0])
        range_data_2 = np.array(range_data[1])
        
        if len(range_data_1) != len(range_data_2) or len(range_data_1[0]) != len(range_data_2[0]):
            return False
        return True
    
    except Exception as ex:
        log_error(f'Response from compare_of_ranges: {ex}')
        return None

async def compare_of_values(data: list) -> Optional[tuple[bool, list[str]]]:
    """
    function to compare values in a table at two points in time

    :param data: A tuple of two lists of lists of strings.
    :return: Tuple of flag and dictionary with changes.
    """
    try:
        flag = np.array_equal(data[0], data[1])
        changes = []
        if not flag:
            for row_index, (row1, row2) in enumerate(zip(data[0], data[1])):
                if row1 != row2:
                    for col_index, (cell1, cell2) in enumerate(zip(row1, row2)):
                        if cell1 != cell2:
                            name_col = await converting_of_number(col_index+1)
                            info = f'{name_col}{row_index+1}: {cell1} -> {cell2}'
                            changes.append(info)
            flag = False
            return flag, changes
        return flag, changes
    
    except Exception as ex:
        log_error(f'Response from compare_of_values: {ex}')
        return None

