from typing import Optional
from datetime import datetime
import aiomysql
import pymysql

from logger import log_debug, log_error

def server_connect_check(host: str, port: int, user: str, password: str) -> Optional[pymysql.Connection]:
    """
    Common server connection check
    """
    try:
        conn = pymysql.connect(host=host,
                                port=port,
                                user=user,
                                password=password
                                )
        log_debug('seccessful server connection')
        return conn
    
    except Exception as ex:
        log_error(f"Server connection error: {ex}")
        return None

async def db_connection_check(host: str, port: int, user: str, password: str, user_id: int) -> Optional[aiomysql.Connection]:
    """Async common server connection check
    """
    try:
        conn = await aiomysql.connect(host=host,
                                        port=port,
                                        user=user,
                                        password=password)
        log_debug(f'User {user_id} has seccessful connectioned to database')
        return conn
    
    except Exception as ex:
        log_error(f"Server connection error: {ex}")
        return None

def create_database(conn: pymysql.Connection, db_name: str) -> None:
    """create database if it doesn't exist
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW DATABASES")
            bases_tuple = cursor.fetchall()
            flag = 0

            for item in bases_tuple:
                if item[0] == 'telegram_users':
                    log_debug(f'database {db_name} already exist')
                    flag += 1

            if flag == 0: 
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
                log_debug(f'database {db_name} successfully created')
            return None
    
    except Exception as ex:
        log_error(f"Response from create_database: {ex}")
        return None

def create_tables(conn: pymysql.Connection, db_name: str) -> None:
    """
    Create tables if these dont exist
    """
    try:
        with conn.cursor() as cursor:
            conn.select_db(db_name)

            cursor.execute("SHOW TABLES LIKE 'telegram_connections'")
            result = cursor.fetchone()

            if result:
                log_debug('tables for telegram_users base already exists')
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_connections
                     
                    (
                        id int(11) NOT NULL AUTO_INCREMENT,
                        user_id int(20) NOT NULL,
                        connection_time DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE KEY (user_id)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS spreadsheets_users_data
                    (
                        id int(11) NOT NULL AUTO_INCREMENT,
                        user_number int(20) NOT NULL,
                        spreadsheets_name varchar(20) NOT NULL,
                        sheet_number int(11) NOT NULL,
                        data_range varchar(20) NOT NULL,
                        interval_value int(11) NOT NULL,
                        PRIMARY KEY (id),
                        FOREIGN KEY (user_number) REFERENCES telegram_connections (id)
                    )
                    """
                )
                log_debug('tables seccessful created')
            return None
        
    except Exception as ex:
        log_error(f"Response from create_tables def: {ex}")
        return None
    
async def insert_new_users(conn: aiomysql.Connection, user_id: int, time: datetime) -> None:
    """
    adding a telegram user ID to the telegram_connections table
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
    Adding data about the tracked table by the user
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
    Extracting user's telegram id from the table
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

async def tracked_tables(conn: aiomysql.Connection, user_id: int) -> Optional[int]:
    """
    extracting all user's spreadsheets for traking
    """
    async with conn.cursor() as cursor:
        try:
            query = "SELECT * FROM telegram_users.spreadsheets_users_data WHERE user_number = %s"
            await cursor.execute(query, user_id)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from tracked_tables def: {ex}")
            return None
        
async def delete_spreadsheets(conn: aiomysql.Connection, table_id: int, user_number: int) -> None:
    """
    User deleting the table from which he receives changes
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

async def user_id_tables(conn: aiomysql.Connection, user_id: int) -> Optional[int]:
    """
    Getting a list of tables from which the user receives changes
    """
    async with conn.cursor() as cursor:
        try:
            query = """SELECT id FROM telegram_users.spreadsheets_users_data WHERE user_number = %s"""
            await cursor.execute(query, user_id)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from user_id_tables def: {ex}")

async def tg_user_id_list(conn: aiomysql.Connection) -> Optional[int]:
    """
    Getting a list of users connected to the telegram bot
    """
    async with conn.cursor() as cursor:
        try:
            query = """SELECT user_id FROM telegram_users.telegram_connections"""
            await cursor.execute(query)
            result = await cursor.fetchall()
            return result
        
        except Exception as ex:
            log_error(f"Response from tg_user_id_list def: {ex}")