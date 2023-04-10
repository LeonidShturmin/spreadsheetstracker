import time
import asyncio
import re
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import telegram
import numpy as np

from config import tg_token

SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SPREADSHEET_NAME = 'testsheet'
# sheet_id = '1rIuEB5OI7bP-_hpXCoL-UllPLPzGnpRT0tjJP0a92z8'
# range_name = 'A1:C5'
start_coordinates = {"leftcol": 'A', "leftrow": 1, "rightcol": 'B', "rightrow":  2}
bot = telegram.Bot(token=tg_token)

# def check_addition_of_rows_columns():

#     credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
#     service = build('sheets', 'v4', credentials=credentials)


#     # Получаем данные из заданного диапазона ячеек
#     result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_name).execute()
#     # rows = len(result.get('values'))
#     # cols = len(result.get('values')[0])
#     return print(result)


def speardsheets_connection_check(account_file, spreadsheet_name, scopes) -> tuple[bool, gspread.worksheet.Worksheet]:
    """
    checking a spreadsheet connection
    """
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(account_file, scopes=scopes)
        file = gspread.authorize(creds)

        workbook = file.open(spreadsheet_name)
        sheets = workbook.sheet1

        return True, sheets
    
    except Exception as ex:
        print(f'Respons from speardsheets_connection_check def..{ex}') # надо записывать это в лог

def extracting_values(sheets: gspread.worksheet.Worksheet, coordinates: dict) -> list: 
    """
    function to retrieve data from a sheet
    """

    range_name = list(coordinates.values())
    cell_values = sheets.range(f'{range_name[0]}{range_name[1]}:{range_name[2]}{range_name[3]}')

    return cell_values

def search_ranges(sheets: gspread.worksheet.Worksheet, users_coordinates: dict):
    """
    the function looks for a range of cells in a spreadsheet that has values
    """
    with open('matching_dictionary.json', 'r') as file:
        matching_dictionary = json.load(file)
    """получаем данные из словаря соответствия названия столбцов и их порядковые номера"""

    right_col = users_coordinates['rightcol']
    """получаем название столбца правого диапазона"""

    column_number = matching_dictionary[right_col]
    """получаем порядковый номер правого столцба"""

    counter = 0
    flag = 0
    while counter != column_number:
        users_coordinates['rightrow'] += 1
        new_cell_values = extracting_values(sheets, users_coordinates)

        for cell in new_cell_values[-column_number:]:
            values = ''.join(re.findall(r'\'(.*?)\'', str(cell)))
            if values == '':
                counter += 1
        
        flag += 1
        users_coordinates['rightrow'] = flag

    print(users_coordinates)
    # if counter == column_number:
    #     column_number += 1 
    #     result = [key for key, value in matching_dictionary.items() if value == column_number]
    #     users_coordinates['rightcol'] = ''.join(result)
    #     # new_cell_values = extracting_values(sheets, users_coordinates)
    #     print(users_coordinates)

# print(new_cell_values)
if __name__ == '__main__':
    sheets_connection = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SPREADSHEET_NAME, SCOPES)
    search_ranges(sheets_connection[1], start_coordinates)





def value_comparison(data)-> tuple[bool, dict[str, list]]:
    """
    function to compare values in a table at two points in time
    """
    flag = True
    changes_info ={"changes": []}
    for i, k in zip(data[0], data[1]):
        if i != k:
            changes_info["changes"].append(f'{i} -> {k}')
            flag = False 

    return flag, changes_info

async def send_message(message):
    """
    sending a message to the chatbot
    """
    await bot.send_message(chat_id=369142557, text=f'{message}')

async def main(waitingtime):

    cell_values_list = []

    while True:
        sheets_connection = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SPREADSHEET_NAME, SCOPES)
        cell_values_list.append(extracting_values(sheets_connection[1], "B", 5))

        if len(cell_values_list) == 2:
            value_comparison_result = value_comparison(cell_values_list)

            if value_comparison_result[0] is False:
                await send_message(value_comparison_result[1])

            cell_values_list.pop(0) 

        time.sleep(waitingtime)

# if __name__ == '__main__':
    # asyncio.run(main(5))