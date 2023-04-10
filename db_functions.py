from datetime import datetime, timezone
from typing import Optional

import time
import pymysql

from config import db_name, host, password, user 

def server_connect() -> pymysql.connections.Connection:
    """server connection check
    """
    try:
        connection = pymysql.connect(host=host,
                                     user=user,
                                     password=password)
        print('successful server connect')
        return connection
    except Exception as ex:
        return print(f'(Response from server_connect def...{ex}')

def connect_test() -> pymysql.connections.Connection:
    """
    database connection check
    """
    try:
        connection = pymysql.connect(
            host=host,
            port=3306,
            user=user,
            password=password,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        print('successful db connect')
        return connection
    except Exception as ex:
        return print(f'(Response from connection test...{ex}')

def create_database():
    """create database if it doesn't exist
    """
    conn = server_connect()
    cursor = conn.cursor()

    try:
        cursor.execute(f"CREATE DATABASE {db_name}")
        return print('database is create')
    except pymysql.err.DatabaseError as ex:
        return print(f'(Response from create_database def...{ex}')
    finally:
        conn.close()

def create_users_table():

    conn = server_connect()
    cursor = conn.cursor()
    cursor.execute(f"USE {db_name}")

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users 
            (
                id int(11) NOT NULL AUTO_INCREMENT,
                user_id int(20) NOT NULL,
                user_name varchar(20) NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        return print('table is create')
    except Exception as ex:
        return print(f'(Response from create_table def...{ex}')
    finally:
        conn.close()

def create_sheets_info_table():

    conn = server_connect()
    cursor = conn.cursor()
    cursor.execute(f"USE {db_name}")

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_tables
            (
                id int(11) NOT NULL AUTO_INCREMENT,
                user_id int(20) NOT NULL,
                spreadsheets_name varchar(20) NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        return print('table is create')
    except Exception as ex:
        return print(f'(Response from create_table def...{ex}')
    finally:
        conn.close()
    
def insert_new_users(user_id: int, user_name: str):
    """
    add a new row to the database
    """
    connection = connect_test()
    try:

        with connection.cursor() as cursor:

            insert_query = "INSERT INTO users (user_id, spreadsheets_name)\
                            VALUES (%s, %s)"
            val = (user_id, user_name)
              
            cursor.execute(insert_query, val )
            connection.commit()

    except Exception as ex:
        return print(f'(Response from insert_new_users def...{ex}')
    finally:
        connection.close()

def insert_new_sheets_info(user_id: str, sheets_name: str):
    """
    add a new sheets name
    """
    connection = connect_test()
    try:

        with connection.cursor() as cursor:

            insert_query = "INSERT INTO user_tables (user_id, spreadsheets_name)\
                            VALUES (%s, %s)"
            val = (user_id, sheets_name)
              
            cursor.execute(insert_query, val)
            connection.commit()

    except Exception as ex:
        return print(f'(Response from insert_new_users def...{ex}')
    finally:
        connection.close()
        
if __name__ == '__main__':
    create_database()
    create_users_table()
    create_sheets_info_table()