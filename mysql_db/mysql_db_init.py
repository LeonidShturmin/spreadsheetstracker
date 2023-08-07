import sys
from typing import Optional
import aiomysql
import pymysql

sys.path.append('logs/')
from logger import log_debug, log_error

def server_connect_check(host: str, port: int, user: str, password: str) -> Optional[pymysql.Connection]:
    """
    Проверка соединения с сервером mysql
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
    """
    Асинхронная функция проверки соединения с сервером mysql
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
    """
    Создание базы данных db_name, если она еще не создана
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
   Создание таблиц в db_name базе данных
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

def setup_db(db_host: str, db_port: int, db_user: str, db_password: str, db_name: str) -> None:
    """
    Инициалиация создания базы данных и таблиц в ней
    """
    connection = server_connect_check(db_host, db_port, db_user, db_password)
    create_database(connection, db_name)
    create_tables(connection, db_name)
