import re
from typing import Optional
from typing import Union, Tuple

import gspread
from gspread.utils import column_letter_to_index
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
import numpy as np

from logs.logger import log_error

async def speardsheets_connection_check(account_file: str, scopes: list, spreadsheet_name: str,
                                  sheet_number: int) -> Union[Tuple[
                                      bool, gspread.worksheet.Worksheet], None]:
    """
    Проверка соединения с Google таблицейн

    :param account_file: файл с правами доступа 
    :param spreadsheet_name: название Google таблицы 
    :param scopes: настройки прав доступа 
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
    Функция принимает номер столбца в гугл таблице и возвращается его буквенное название
    например колонка 27 будет конвертирована в АА
    """
    ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
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
    Функция обращается к заданной пользователем Google таблице двумя способами:
    1) в случае, если пользователю передал координаты в формате A1:B1, функция возвращает значения
    ячеек в этом диапазоне посредством метода .range
    2) Если пользователь не передал координаты, то метод .get_all_values() возвращает значения всех заполенных ячеек и коорднаты заполненнго диапазона
    """
    user_coordinates = {"leftcol": 'A', "leftrow": 1,
                        "rightcol": 'A', "rightrow":  1}
    pattern = r"^[A-Z]+[0-9]+:[A-Z]+[0-9]+$"
    all_values = []
    try:
        if start_coords is None or start_coords == 'dynamic': # случай №2
            all_values = sheets.get_all_values() # возврат значений всех заполенных ячеек 
            number_of_columns = len(all_values[0])

            user_coordinates['rightrow'] = len(all_values)
            user_coordinates['rightcol'] = await converting_of_number(
                number_of_columns)

        else: # случай №1
            match = re.match(pattern, start_coords) # проверка корректности передачи диапазона в start_coords

            if match is None:
                return False, False
            values = sheets.range(start_coords) # возврат значений из заданного пользователем диапазона, если он корректно передан в аргумент start_coords

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
    Функция проверяет размеры массивов (заполенных диапазонов в Google таблице). Относится к случаю №2 из функции search_ranges
    :range_data: двумерный массив значений ячеек в таблице в два промежутка времени
    """
    try:
        range_data_1 = np.array(range_data[0])
        range_data_2 = np.array(range_data[1])
        
        if len(range_data_1) != len(range_data_2) or len(range_data_1[0]) != len(range_data_2[0]): # сравнением массивов длине и ширине
            return False
        
        return True
    
    except Exception as ex:
        log_error(f'Response from compare_of_ranges: {ex}')
        return None

async def compare_of_values(data: list) -> Optional[tuple[bool, list[str]]]:
    """
    Функция сравнивает значения ячеек в два промежутка времени 
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

