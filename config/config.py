import os

from dotenv import load_dotenv

load_dotenv()

# path = '../run/secrets/token'
# with open(path, "r") as file:
#     tg_token = file.read()
tg_token = "5943787736:AAFbM82rcJGu16G2bzGtQuhzeH_ioRQj2kc"
db_name = os.getenv('MYSQL_DATABASE')
host = os.getenv('MYSQL_HOST')
port = int(os.getenv('MYSQL_PORT'))
password = os.getenv('MYSQL_ROOT_PASSWORD')
user = os.getenv('MYSQL_USER')
SERVICE_ACCOUNT_FILE = 'credentials/credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
