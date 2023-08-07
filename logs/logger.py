import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.FileHandler('logs/logs.log')
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

logger_list = ['aiogram', 'asyncio', 'urllib3', "google.auth", 'pymorphy2']

for i in logger_list:
    logging.getLogger(i).setLevel('ERROR')

def log_debug(msg: str):
    """
    dfdfdfdfd
    """
    logger.debug(msg, exc_info=False)

def log_error(msg: str):
    """
    dfdfddf
    """
    logger.error(msg, exc_info=False)
