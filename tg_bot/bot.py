import sys
import datetime
import json

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

for folders in ['logs/', 'mysql_db/', 'tg_bot/', 'config/']:
    sys.path.append(folders)

from functions import speardsheets_connection_check, search_ranges, compare_of_values, compare_of_ranges
from mysql_db_init import db_connection_check, setup_db
from db_functions import user_id_tables, tg_user_id_list, insert_new_users, insert_new_sheets_info
from db_functions import extraction_query, tracked_tables, delete_spreadsheets
from config import SERVICE_ACCOUNT_FILE, SCOPES, tg_token, host, port, user, db_name, password
from logger import log_error

with open('tg_bot/messages.json', 'r') as file:
    messages_dict = json.load(file)

bot = Bot(token=tg_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class UserState(StatesGroup):
    """
    Описание пользовательских состояний 
    """
    table_name = State()
    sheet_number = State()
    range = State()
    interval = State()
    tables_manage = State()

async def bot_messages(key: str, language_code: str) -> str:
    """
    Функция обращается к словарю messages_dict из файла messages.json с текстовыми переменными
    и возвращает сообщение в зависимости от выбранного пользователем языка
    """
    text = messages_dict[key][language_code]
    return text

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """
    Установка пользователем языка
    """
    markup = InlineKeyboardMarkup()
    item_1 = InlineKeyboardButton(text="🇷🇺 Русский", callback_data="Russian")
    item_2 = InlineKeyboardButton(text="🇬🇧 English", callback_data="English")
    markup.add(item_1, item_2)

    await message.answer(text="Выбери язык/Choose language:", reply_markup=markup)

@dp.callback_query_handler(lambda callback_query: callback_query.data in ["Russian", "English"])
async def general_instruction(callback_query: types.CallbackQuery):
    """
    Функция направляет пользователю инструкцию о том, какие шаги нужно сделать, чтобы начать
    отслеживать изменения в Google таблица.
    """
    global language
    if callback_query.data == "Russian":
        language = 'ru'
    else:
        language = 'eng'

    try:
        now = datetime.datetime.now()
        user_id = callback_query.message.chat.id
        connection = await db_connection_check(host, port, user, password, user_id)
        users_telegram_id = [value[0] for value in await tg_user_id_list(connection)]

        if user_id not in users_telegram_id: # проверка на то, подключался ли ранее пользователь к боту
            await insert_new_users(connection, user_id, now) # добавление нового пользователя в бд
            text_1 = await bot_messages("fisrt_instruction", language)
            text_2 = await bot_messages("add_account_bottom", language)

            markup = InlineKeyboardMarkup()
            item = InlineKeyboardButton(text=text_2, callback_data="account_added")
            markup.add(item)
            await bot.send_message(chat_id=user_id, text=text_1, parse_mode="HTML", reply_markup=markup)

        else: 
            markup = InlineKeyboardMarkup()
            item = InlineKeyboardButton(
                text="bup", callback_data="account_added")
            markup.add(item)
            await bot.send_message(chat_id=user_id, text='Welcome back', parse_mode=None, reply_markup=markup)

    except Exception as ex:
        log_error(f"Respone from general_instruction: {ex}")

@dp.callback_query_handler(lambda callback_query: callback_query.data in ["account_added", "retry"])
async def account_added_handler(callback_query: types.CallbackQuery):
    """
    Функция отлавливает нажатие кнокпи "account_added" и "retry", устанавливает состояние UserState.table_name,
    предлагает ввести название таблицы
    """
    user_id = callback_query.message.chat.id
    text=await bot_messages("spreadsheet_name", language)

    await UserState.table_name.set()
    await bot.send_message(chat_id=user_id, text=text)

@dp.message_handler(state=UserState.table_name)
async def enter_table_name(message: types.Message, state: FSMContext):
    """
    Функция перехватает установку состояния UserState.table_name, принимает название таблицы из функции account_added_handler,
    записывает его state.proxy() и устанавливает следующее состояние UserState.sheet_number
    """
    async with state.proxy() as data:
        data['table_name'] = message.text
    text = await bot_messages("page_number", language)

    await UserState.sheet_number.set()
    await message.answer(text=text)

@dp.message_handler(state=UserState.sheet_number)
async def enter_sheet_number(message: types.Message, state: FSMContext):
    """
    Функция перехватает установку состояния UserState.sheet_number, принимает номер листа из функции enter_table_name,
    записывает его state.proxy() и вызывает функцию connection_check, которая проверяет соединение с гугл таблицей
    """
    text_1 = await bot_messages("sheet_conn", language)
    text_2 = await bot_messages("input_check", language)
    
    try:
        user_id = message.chat.id
        try:
            sheet_number = int(message.text)

            async with state.proxy() as data:
                data['sheet_number'] = sheet_number

            await state.reset_state(with_data=False)
            await message.answer(text=text_1)
            await connection_check(user_id, state)

        except ValueError:
            await bot.send_message(chat_id=user_id,
                                text=text_2)
            
    except Exception as ex:
        log_error(f"Respone from enter_sheet_number: {ex}")

async def connection_check(user_id, state: FSMContext):
    """
    Функция вызывается внутри enter_sheet_number, проверяет соединение с google таблицей по введенным пользователям данным
    если соединение успешно установлено, пользователю предлагается выбрать тип отслеживания таблицы: полный, фиксированный. 
    Если соединение не установлено, пользователю предлагается проверить введенные ранее данные и ввести их заново
    """
    try:
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']
            conn = await speardsheets_connection_check(
                SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number) # проверка соединения с Google таблицей

        if conn[0]: # если соединение успешно установлено, пользователь выбирает тип отслеживания
            text_1 = await bot_messages("input_renge_1", language)
            text_2 = await bot_messages("input_renge_2", language)
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=text_1, callback_data="dynamic"),
                        types.InlineKeyboardButton(
                            text=text_2, callback_data="fix"),
                    ]
                ]
            )
            text_3 = await bot_messages("succes_conn", language)
            await bot.send_message(chat_id=user_id, text=text_3, parse_mode="HTML", reply_markup=keyboard)

        else: # если соединение не установлено, то предлагается проверить данные и ввести их заново
            text_4 = await bot_messages("retry", language)
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=text_4, callback_data="retry"),
                    ]
                ]
            )
            text_5 = await bot_messages("conn_error", language)
            await bot.send_message(
                chat_id=user_id, text=text_5.format(table_name, sheet_number), reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as ex:
        log_error(f"Respone from connection_check: {ex}")
    
@dp.callback_query_handler(lambda callback_query: callback_query.data in ["dynamic", "fix"])
async def range_input(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Функция перехватывает нажатие кнопок "dynamic" и "fix". 
    Если пользователь выбрал "fix", то состояние переключается на UserState.range и пользователю предлагается ввести диапазон
    Если пользователь выбрал "dynamic", состояние переключается на UserState.interval, пользователю предлагается ввести интервал отслеживания
    search_ranges определяет заполненный в таблице диапазон и вовзращает его коориднаты формата A1:B1
    """
    try:
        user_id = callback_query.message.chat.id
        text_1 = await bot_messages("enter_range", language)

        if callback_query.data == 'fix':
            await UserState.range.set() # установка состояния FSMContext для перехвата его функцией range_interval
            await bot.send_message(chat_id=user_id, text=text_1, parse_mode="HTML")

        elif callback_query.data == 'dynamic':
            await UserState.interval.set() # установка состояния FSMContext для перехвата его функцией interavl_input
            async with state.proxy() as data:
                table_name = data['table_name']
                sheet_number = data['sheet_number']

            conn = await speardsheets_connection_check(
                SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number) # установка соединения с Google таблицей
            all_data = await search_ranges(conn[1])  # поиск заполненного диапазона и возврат его кооридинат

            left = all_data[0]['leftcol'] + str(all_data[0]['leftrow'])
            right = all_data[0]['rightcol'] + str(all_data[0]['rightrow'])
            start_range = left + ":" + right

            async with state.proxy() as data:
                data['range'] = 'dynamic'

            text_2 = await bot_messages("set_interval_1", language)
            await bot.send_message(chat_id=user_id,
                                text=text_2.format(start_range))
    except Exception as ex:
        log_error(f"Respone from range_input: {ex}")

@dp.message_handler(state=UserState.range)
async def range_interval(message: types.Message, state: FSMContext):
    """
    Функция перехватывает состояние UserState.range, установленное в функции range_input, и принимает введенный интервал отслеживания
    Если пользовательские коориднаты диапазона введены корректно, функция устанавливает состояние UserState.interval
    """
    try:
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']

        conn = await speardsheets_connection_check(
            SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number) # установка соединения с Google таблицей
        cell_values = await search_ranges(conn[1], message.text) # Функция пытается вернуться значения ячеек из Google таблицы
        #по пользовательским коориднатам, если координаты введены некорректно, функция возвращает False
        
        if False in cell_values:
            text_1 = await bot_messages("wrong_range", language)
            await message.answer(text=text_1, parse_mode="HTML")

        else:
            await UserState.interval.set()
            async with state.proxy() as data:
                data['range'] = message.text

            text_2 = await bot_messages("set_interval_2", language)
            await message.answer(text=text_2)

    except Exception as ex:
        log_error(f"Respone from range_interval: {ex}")

@dp.message_handler(state=UserState.interval)
async def interavl_input(message: types.Message, state: FSMContext):
    """
    Функция перехватывает состояние UserState.interval устанавливаемое в функциях range_interval и range_input
    Если период отслеживания введен корректно (целое неотрицательное число), то пользователю
    предлагается запустить процесс отслеживания изменений в таблице
    """
    user_id = message.chat.id
    text_1 = await bot_messages("start_tracking", language)
    try:
        async with state.proxy() as data:
            data["interval_value"] = int(message.text) * 60

        markup = InlineKeyboardMarkup()
        item = InlineKeyboardButton(
            text=text_1, callback_data="starting")
        markup.add(item)
        text_2 = await bot_messages("notice", language)

        await state.reset_state(with_data=False) #сброс состояний FSMContext
        await message.answer(text_2.format(message.text), parse_mode="HTML", reply_markup=markup)

    except ValueError:
        text_3 = await bot_messages("wrong_interval", language)
        await bot.send_message(chat_id=user_id,
                               text=text_3)

async def sheets_manage(user_id: int):
    """
    После нажатия кнопки "starting" в функции interavl_input, пользователю возвращается меню из двух кнопок
    'Add table' - позволяет пользователю добавить новую таблицу для отслеживания
    'Delete table' - позволяет просмотреть список отслеживаемых таблиц, удалить выбранную из списка таблицу
    """
    text_1 = await bot_messages("add_table", language)
    text_2 = await bot_messages("delete_table", language)
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        commands = [text_1, text_2]
        keyboard.add(*commands)
        text_3 = await bot_messages("notice_2", language)

        await bot.send_message(chat_id=user_id, text=text_3, reply_markup=keyboard)
    
    except Exception as ex:
        log_error(f"Respone from search_comparisons_init: {ex}")

async def loop(table_name: str, sheet_number: int, user_range: str, user_id: str , state: FSMContext) -> None: 
    """
    Функция поиска изменений с заданной периодичностью interval в google таблице.
    Вызывается в функции search_comparisons_init
    """
    cell_values_list = []
    while True: 
        conn = await speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number) # возвращает соединение с google таблицей
        cell_values = await search_ranges(conn[1], user_range) # возвращает массив значений в ячейках в зависимости от заданного user_range (dynamic или  fix)
        cell_values_list.append(cell_values[1]) 

        # Форматирование кооридинат из cell_values[0] = {'leftcol': 'A', 'leftrow': 1, 'rightcol': 'A', 'rightrow': 3} в формат A1:A3
        current_range = f"{cell_values[0]['leftcol']}{cell_values[0]['leftrow']}:{cell_values[0]['rightcol']}{cell_values[0]['rightrow']}"

        if len(cell_values_list) == 2: # если в cell_values_list находятся значения ячеек за 2 промежутка времени одного и того же диапазона
            # то начинается поиск различий между cell_values_list[0] и cell_values_list[1] 
            range_changes = await compare_of_ranges(cell_values_list) # сравнение размеров массивов google таблицы за 2 промежутка времени
            value_comparison_result = await compare_of_values(cell_values_list) # сравнение значений массивов google таблицы за 2 промежутка времени

            if range_changes is False: # если размер массива (диапазон отслеживания) изменился, то пользователю направляется инфо о новном диапазоне
                await bot.send_message(chat_id=user_id, text=f"New Range {current_range}")
            
            if value_comparison_result[0] is not True: # если различия в массивах есть, то пользователю направляются ссылки на ячейки, изменившие свои значения
                for i in value_comparison_result[1]:
                    await bot.send_message(chat_id=user_id, text=f"Table: {table_name}, sheet: {sheet_number}, сell: {i}")

            cell_values_list.pop(0) # удаление первого по времени добавления массива значений ячеек из google таблицы

@dp.callback_query_handler(lambda callback_query: callback_query.data == "starting")
async def search_comparisons_init(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Основная функция. После нажатия кнопки "starting" запускается процесс поиска и отправки пользователю
    изменений в таблице с заданной периодичностью interval
    Также пользователю направляется меню с 2 кнопками ['Add table', 'Delete table'] для управления своими таблицами 
    """
    user_id = callback_query.message.chat.id
    connection = await db_connection_check(host, port, user, password, user_id)
    user_number = await extraction_query(connection, user_id) # извлечение номера пользователя в бд

    async with state.proxy() as data: 
        table_name = data['table_name']
        sheet_number = data['sheet_number']
        user_range = data['range']
        interval_value = data['interval_value']

    await insert_new_sheets_info(connection, user_number, table_name, sheet_number, user_range, interval_value, user_id) 
    try:
        user_id = callback_query.message.chat.id
        await sheets_manage(user_id) 
        await loop(table_name, sheet_number, user_range, user_id, state)
        await asyncio.sleep(interval_value)
        asyncio.create_task(loop())
    
    except Exception as ex:
        log_error(f"Respone from search_comparisons_init: {ex}")
    
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def command_handler(message: types.Message):
    """
    Функция отлавливает нажатие кнопок из функции sheets_manage и реализует их функционал
    """
    try:
        user_id = message.chat.id
        connection = await db_connection_check(host, port, user, password, user_id)
        user_number = await extraction_query(connection, user_id)
        user_tables = await tracked_tables(connection, user_number)

        if message.text in ['Add table', 'Добавить таблицу']:
            text_1 = await bot_messages("spreadsheet_name", language)
            await UserState.table_name.set() # Устанавливает пользователю состояние UserState.table_name 
            await bot.send_message(chat_id=message.chat.id, text=text_1) # Принимает на ввод название таблицы и возвращает к функции enter_table_name

        elif message.text in ['Delete table', 'Удалить таблицу']:
            user_tables_id = [value[0] for value in await user_id_tables(connection, user_number)] # возвращает список отслеживаемых таблиц

            if len(user_tables_id) == 0: # если пользователь не отслеживает ни одной таблицы 
                text_2 = await bot_messages("empty_table_list", language)
                await bot.send_message(chat_id=message.chat.id, text=text_2)
            else:
                text_3 = await bot_messages("table_select", language)
                await UserState.tables_manage.set() # Устанавливает состояние UserState.tables_manage и принимает номер таблицы для удаления
                await bot.send_message(chat_id=message.chat.id, text=text_3)

                for rows in user_tables:
                    text_4 = await bot_messages("table_info", language)
                    await bot.send_message(chat_id=message.chat.id, text=text_4.format(rows[0], rows[2], rows[3], rows[4], rows[5]), parse_mode="HTML")

    except Exception as ex:
        log_error(f"Respone from command_handler: {ex}")
    
@dp.message_handler(state=UserState.tables_manage)
async def manage_table(message: types.Message, state: FSMContext):
    """
    Функция перехватывает состояние UserState.tables_manage, установленное в функции command_handler
    """
    user_id = message.chat.id
    connection = await db_connection_check(host, port, user, password, user_id)
    user_number = await extraction_query(connection, user_id) # номер пользователя в базе
    user_tables_id = [value[0] for value in await user_id_tables(connection, user_number)] # кол-во отслеживаемых пользователем таблиц
    try:
        table_id = int(message.text)
        if table_id in user_tables_id: # если пользователь ввел номер таблицы и она присутствует в перечне, то функция delete_spreadsheets удаляет ее из бд
            text_1 = await bot_messages("succes_delete", language)
            await delete_spreadsheets(connection, table_id, user_number)
            await bot.send_message(chat_id=message.chat.id, text=text_1)
            await state.finish()

        elif table_id not in user_tables_id and user_tables_id != []:
            text_2 = await bot_messages("non_existent_table", language)
            await bot.send_message(chat_id=message.chat.id, text=text_2)
            await state.finish()

        elif len(user_tables_id) == 0:
            text_3 = await bot_messages("empty_table_list", language)
            await bot.send_message(chat_id=message.chat.id, text=text_3)
            await state.finish()

    except ValueError:
        text_4 = await bot_messages("input_check", language)
        await bot.send_message(chat_id=message.chat.id, text=text_4)

if __name__ == '__main__':
    setup_db(host, port, user, password, db_name)
    executor.start_polling(dp, skip_updates=True)
