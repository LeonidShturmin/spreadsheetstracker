import os

from dotenv import load_dotenv

load_dotenv()

tg_token = os.getenv('TELEGRAM_TOKEN')
db_name = os.getenv('DB_NAME')
host = os.getenv('HOST')
password = os.getenv('PASSWORD')
user = os.getenv('USER_NAME')