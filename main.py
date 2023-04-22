import time
import asyncio
import re
import json
import logging

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from typing import Union, Tuple
import telegram
import numpy as np

from config import tg_token

logging.basicConfig(level='ERROR', filename='logs.log')
logger = logging.getLogger()

SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SPREADSHEET_NAME = 'testsheet'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

start_coordinates = {"leftcol": 'A', "leftrow": 1, "rightcol": 'B', "rightrow":  1}
bot = telegram.Bot(token=tg_token)

def speardsheets_connection_check(account_file: str, spreadsheet_name: str,
                                  scopes: list, sheet_number: int) -> Union[Tuple[
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
        creds = ServiceAccountCredentials.from_json_keyfile_name(account_file, scopes=scopes)
        file = gspread.authorize(creds)

        workbook = file.open(spreadsheet_name)
        sheets = workbook.get_worksheet(sheet_number - 1)
        return True, sheets
    
    except GoogleAuthError as ex:
        logger.error('Error {}', ex)
        return False

    except HttpError as ex:
        logger.error('Error %s', ex)
        return False

    except gspread.exceptions.GSpreadException as ex:
        logger.error('Error %s', ex.__class__.__name__)
        return False

    except TimeoutError as ex:
        logger.error('Error %s', ex)
        return False

    except ConnectionError as ex:
        logger.error('Error %s', ex)
        return False

    except ValueError as ex:
        logger.error('Error %s', ex)
        return False

    except Exception as ex:
        logger.error('Error %s' % (ex.__class__.__name__))
        return False

# def extracting_values(sheets: gspread.worksheet.Worksheet, coordinates: dict) -> list: 
#     """
#     function to retrieve data from a sheet
#     """
#     range_name = list(coordinates.values())
#     cell_values = sheets.range(f'{range_name[0]}{range_name[1]}:{range_name[2]}{range_name[3]}')

#     return cell_values

def converting_of_number(number: int) -> str:
    """
    the function takes as input the column number (str)
    and returns its letter match in the spreadsheet
    for example column number 27 is AA in the google spreadsheet
    """
    if number // 26 == 0:
        col_name = ALPHABET[number - 1]
    else:
        col_name = ALPHABET[number // 26 - 1] + ALPHABET[number % 26 - 1]

    return col_name

def search_ranges(sheets: gspread.worksheet.Worksheet, user_coordinates: dict) -> tuple[dict, list]:
    """
    the function looks for a range of cells in a spreadsheet with values.
    Returns the coordinates of a range and a list of values in that range  
    """
    all_values = sheets.get_all_values()
    user_coordinates['rightrow'] = len(all_values)
    number_of_columns = len(all_values[0])
    user_coordinates['rightcol'] = converting_of_number(number_of_columns)

    return user_coordinates, all_values

def compare_of_ranges(range_data: list) -> bool:
    """
    the function compares the range size. If the range has changed,
    the number of added rows and columns is returned
    
    :range_data: two-dimensional array with data from a table at 2 points in time
    """
    row_info = 0
    col_info = 0
    range_data_1 = np.array(range_data[0])
    range_data_2 = np.array(range_data[1])

    if len(range_data_1) != len(range_data_2):
        rows_difference = len(range_data_2) - len(range_data_1)
        row_info = 'Added {} rows'.format(rows_difference)

    if len(range_data_1.transpose()) != len(range_data_2.transpose()):
        col_difference = len(range_data_2.transpose()) - len(range_data_1.transpose())
        col_info = 'Added {} cols'.format(col_difference)

    return row_info, col_info

def compare_table_values(data: list) -> tuple[bool, list[str]]:
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
                        info = f'Changes {name_col}{row_index+1} - {cell1} -> {cell2}'
                        changes.append(info)
        flag = False
        return flag, changes
    
    return flag, changes

async def send_message(message):
    """
    sending a message to the chatbot
    """
    await bot.send_message(chat_id=369142557, text=f'{message}')

async def main(waitingtime):

    cell_values_list = []

    while True:
        sheets_connection = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SPREADSHEET_NAME, SCOPES, 1)
        cell_values = search_ranges(sheets_connection[1], start_coordinates)
        cell_values_list.append(cell_values[1])

        if len(cell_values_list) == 2:
            print(compare_of_ranges(cell_values_list)[0])
            print(compare_of_ranges(cell_values_list)[1])
            value_comparison_result = compare_table_values(cell_values_list)
            print(value_comparison_result)
            # await send_message(value_comparison_result[1])
            cell_values_list.pop(0) 

        time.sleep(waitingtime)

if __name__ == '__main__':
    asyncio.run(main(5))
