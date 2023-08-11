import os

from dotenv import load_dotenv

load_dotenv()

path = '../run/secrets/token'
with open(path, "r") as file:
    tg_token = file.read()

db_name = os.getenv('MYSQL_DATABASE')
host = os.getenv('MYSQL_HOST')
port = int(os.getenv('MYSQL_PORT'))
password = os.getenv('MYSQL_ROOT_PASSWORD')
user = os.getenv('MYSQL_USER')
SERVICE_ACCOUNT_FILE = 'app/credentials/credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
