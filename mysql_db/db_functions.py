import sys
from typing import Optional
from datetime import datetime

import aiomysql

sys.path.append('logs/')
from logger import log_debug, log_error

async def insert_new_users(conn: aiomysql.Connection, user_id: int, time: datetime) -> None:
    """
    Добавление нового пользователя в базу данных в таблицу telegram_connections

    conn: соединение с базой данных
    user_id: телеграм ID пользователя
    time: время первого подсоединения к боту пользователем
    """ 
    try:
        async with conn.cursor() as cursor:
            insert_query = "INSERT INTO telegram_users.telegram_connections (user_id, connection_time)\
                            VALUES (%s, %s)"
            val = (user_id, time)
              
            await cursor.execute(insert_query, val)
            await conn.commit()
        log_debug(f'User {user_id} has added successfully')
        return None
    
    except Exception as ex:
        log_debug(f"Response from insert_new_users def: {ex}")
        return None

async def insert_new_sheets_info(conn: aiomysql.Connection,
                                  user_number: int,
                                  sheet_name: str,
                                  sheet_number: int,
                                  data_range: str,
                                  interval_value: int,
                                  user_id: int) -> None:
    """
    Добавление в базу данных информации о гугл таблице пользователя

    conn: соединение с базой данных
    user_number: номер пользователя в базе (не путать с телеграм ID)
    sheet_name: название таблицы
    sheet_number: номер листа таблицы 
    data_range: диапазон отслеживание. Либо в формате A1:B1, либо 'dynamic'
    interval_value: интервал проверки изменений в таблице в минутах
    user_id: телеграм ID пользователя
    """
    try:
        async with conn.cursor() as cursor:
            insert_query = "INSERT INTO telegram_users.spreadsheets_users_data\
                            (user_number, spreadsheets_name, sheet_number, data_range, interval_value)\
                            VALUES (%s, %s, %s, %s, %s)"
            val = (user_number, sheet_name, sheet_number, data_range, interval_value)

            await cursor.execute(insert_query, val)
            await conn.commit()
        log_debug(f"User {user_id} has spreadsheet info added")
        return None
    
    except Exception as ex:
        log_error(f"Response from insert_new_sheets_info def: {ex}")
        return None

async def extraction_query(conn: aiomysql.Connection, user_id: int) -> None:
    """
    Извлечение номера пользователя в базе по его телеграм ID

    conn: соединение с базой данных
    user_id: телеграм ID пользователя
    """
    async with conn.cursor() as cursor:
        try:
            query = "SELECT ID FROM telegram_users.telegram_connections WHERE user_id = %s"
            await cursor.execute(query, user_id)
            result = await cursor.fetchone()

            if result:
                return result[0]
            return None
        
        except Exception as ex:
            log_error(f"Response from extraction_query def: {ex}")
            return None

async def tracked_tables(conn: aiomysql.Connection, user_number: int) -> Optional[list]:
    """
    Извлечение информации о таблицах, которые отслеживает пользователь

    conn: соединение с базой данных
    user_number: номер пользователя в базе
    """
    async with conn.cursor() as cursor:
        try:
            query = "SELECT * FROM telegram_users.spreadsheets_users_data WHERE user_number = %s"
            await cursor.execute(query, user_number)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from tracked_tables def: {ex}")
            return None
        
async def delete_spreadsheets(conn: aiomysql.Connection, table_id: int, user_number: int) -> None:
    """
    Удаление пользовательской информации об отслеживаемой таблице. После удаления из базы
    изменения в этой таблице пользователю приходить не будут. 

    conn: соединение с базой данных
    table_id: номер таблицы пользователя 
    user_number: номер пользователя в базе
    """
    async with conn.cursor() as cursor:
        try:
            query = """DELETE FROM telegram_users.spreadsheets_users_data
                       WHERE id = %s and user_number = %s"""
            await cursor.execute(query, (table_id, user_number))
            await conn.commit()
            log_debug(f"User {user_number} has deleted a table")

        except Exception as ex:
            log_error(f"Response from delete_spreadsheets def: {ex}")

async def user_id_tables(conn: aiomysql.Connection, user_number: int) -> Optional[list]:
    """
    Получение номеров отслеживаемых пользователем таблиц

    conn: соединение с базой данных
    user_number: номер пользователя в базе
    """
    async with conn.cursor() as cursor:
        try:
            query = """SELECT id FROM telegram_users.spreadsheets_users_data WHERE user_number = %s"""
            await cursor.execute(query, user_number)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from user_id_tables def: {ex}")

async def tg_user_id_list(conn: aiomysql.Connection) -> Optional[list]:
    """
    Получение списка подсоединенных к боту пользователей

    conn: соединение с базой данных
    """
    async with conn.cursor() as cursor:
        try:
            query = """SELECT user_id FROM telegram_users.telegram_connections"""
            await cursor.execute(query)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from tg_user_id_list def: {ex}")
