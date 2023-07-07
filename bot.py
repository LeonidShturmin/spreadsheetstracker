import datetime

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from functions import speardsheets_connection_check, search_ranges, compare_of_values, compare_of_ranges
from db_functions import server_connect_check, db_connection_check, create_database
from db_functions import create_tables, insert_new_users, insert_new_sheets_info, extraction_query, tracked_tables, delete_spreadsheets

from config import tg_token, SERVICE_ACCOUNT_FILE, SCOPES, host, password, user, db_name

bot = Bot(token=tg_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

def setup_db(host: str, user: str, password: str) -> None:
    """
    database initialization
    """
    connection = server_connect_check(host, user, password)
    create_database(connection, db_name)
    create_tables(connection, db_name)

setup_db(host, user, password)

class UserState(StatesGroup):
    """
    the class describes user states
    """
    table_name = State()
    sheet_number = State()
    range = State()
    interval = State()
    tables_manage = State()
    
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """
    Start function with instruction
    """
    connection = await db_connection_check(host, user, password)
    user_id = message.from_user.id
    now = datetime.datetime.now()
    await insert_new_users(connection, user_id, now)
    text = """Привет, для того, чтобы начать отслеживать изменения в таблице тебе необходимо:

1. Добавить для чтения сервис аккаунт в настройках доступа таблицы
   googlesheetsaccess@sheetsauto-382306.iam.gserviceaccount.com

2. Написать боту название таблицы в точности соблюдая регистр

3. Перечислить через запятую номера листов для отслеживания. Например: 1, 3, 5"""
    markup = InlineKeyboardMarkup()
    item = InlineKeyboardButton(
        text="Сервис аккаунт добавлен", callback_data="account_added")
    markup.add(item)

    await message.answer(text=text, parse_mode=None, reply_markup=markup)

@dp.callback_query_handler(lambda callback_query: callback_query.data in ["account_added", "retry"])
async def account_added_handler(callback_query: types.CallbackQuery):
    """
    the function catches clicking the "Сервис аккаунт добавлен" button and
    prompts you to input the table name, setting the FSM to the UserState.table_name state
    """
    if callback_query.data in ["account_added", "retry"]:
        user_id = callback_query.message.chat.id
        await UserState.table_name.set()
        await bot.send_message(chat_id=user_id, text="Напиши название таблицы")

@dp.message_handler(state=UserState.table_name)
async def enter_table_name(message: types.Message, state: FSMContext):
    """
    the function is called after entering the table name,
    prompts you to enter the sheet number and puts the FSM in the UserState.sheet_number state
    """
    async with state.proxy() as data:
        data['table_name'] = message.text

    await UserState.sheet_number.set()
    await message.answer("Напиши номер/номера листов")

@dp.message_handler(state=UserState.sheet_number)
async def enter_sheet_number(message: types.Message, state: FSMContext):
    """
    the function is called after entering the sheet number,
    resets all FSM states and displays a message "Проверяем соединение с таблицей.."
    """
    user_id = message.chat.id
    try:
        sheet_number = int(message.text)

        async with state.proxy() as data:
            data['sheet_number'] = sheet_number

        await state.reset_state(with_data=False)
        await message.answer("Проверяем соединение с таблицей..")
        await connection_check(user_id, state)

    except ValueError:
        await bot.send_message(chat_id=user_id,
                               text="Номер листа должен быть целым числом, введите еще раз")

async def connection_check(user_id, state: FSMContext):
    """
    the function is called after enter_sheet_number(), checks the connection
    with the spreadsheet and offers to re-enter the data if the connection failed
    """
    async with state.proxy() as data:
        table_name = data['table_name']
        sheet_number = data['sheet_number']
        conn = speardsheets_connection_check(
            SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)

    if conn[0]:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="Отслеживать целиком", callback_data="dynamic"),
                    types.InlineKeyboardButton(
                        text="Фиксированный диапазон", callback_data="fix"),
                ]
            ]
        )
        await bot.send_message(chat_id=user_id, text="""&#x2705; Соединение успешно установлено 

Выбери тип отслеживания:

<strong>"Полное отслеживание"</strong> - диапазон определится автоматически
и будет расширяться динамически при добавление новых строк или столбцов. 

<strong>"Фиксированный диапазон"</strong> - необходимо задать один или несколько диапазонов

В случае если диапазонов несколько, необходимо перечислить их через запятую.
<strong>Например</strong>: <code>A1:B4, A4:C6</code>""", parse_mode="HTML", reply_markup=keyboard)

    else:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="Ввести данные заново", callback_data="retry"),
                ]
            ]
        )
        await bot.send_message(chat_id=user_id, text="""\u274C Ошибка соединения...
Проверь данные:

Название таблицы - {}

Номер листа - {}""".format(table_name, sheet_number), reply_markup=keyboard)

@dp.callback_query_handler(lambda callback_query: callback_query.data in ["dynamic", "fix"])
async def range_input(callback_query: types.CallbackQuery, state: FSMContext):
    """
    The function is called when the FSM state changes to UserState.range
    after the button is clicked "Отслеживать целиком"
    """
    user_id = callback_query.message.chat.id

    if callback_query.data == 'fix':
        await UserState.range.set()
        await bot.send_message(chat_id=user_id, text="Введите диапазон")

    elif callback_query.data == 'dynamic':
        await UserState.interval.set()
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']

        conn = speardsheets_connection_check(
            SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
        all_data = search_ranges(conn[1])

        left = all_data[0]['leftcol'] + str(all_data[0]['leftrow'])
        right = all_data[0]['rightcol'] + str(all_data[0]['rightrow'])
        start_range = left + ":" + right

        async with state.proxy() as data:
            data['range'] = 'dynamic'

        await bot.send_message(chat_id=user_id,
                               text=f"Стартовый диапазон - {start_range}. Осталось задать интервал обновлений в минутах")

@dp.message_handler(state=UserState.range)
async def range_interavl(message: types.Message, state: FSMContext):
    """
    afdsfdsfsd
    """
    async with state.proxy() as data:
        table_name = data['table_name']
        sheet_number = data['sheet_number']

    conn = speardsheets_connection_check(
        SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
    cell_values = search_ranges(conn[1], message.text)

    if cell_values[0] is None:
        await message.answer("Диапазон должнен быть формата <code>A1:B4</code> латинскими буквами. Введите заново", parse_mode="HTML")

    else:
        await UserState.interval.set()
        async with state.proxy() as data:
            data['range'] = message.text

        await message.answer("Осталось задать интервал обновлений в минутах")

@dp.message_handler(state=UserState.interval)
async def interavl_input(message: types.Message, state: FSMContext):
    """
    sdfdsfdsfds
    """
    user_id = message.chat.id
    try:
        async with state.proxy() as data:
            data['interval_value'] = int(message.text)

        markup = InlineKeyboardMarkup()
        item = InlineKeyboardButton(
            text="Начать отслеживание", callback_data="starting")
        markup.add(item)

        await state.reset_state(with_data=False)
        await message.answer(f"Готово! Интервал изменений - {message.text} (минут)", parse_mode=None, reply_markup=markup)

    except ValueError:
        await bot.send_message(chat_id=user_id,
                               text="Интервал должен быть целым числом, введите еще раз")
        
@dp.callback_query_handler(lambda callback_query: callback_query.data == "starting")
async def some_function(callback_query: types.CallbackQuery, state: FSMContext):
    """
    funcion creates a menu with 3 commands which help to manage a spreadsheets
    adds all datas about spreadsheets (table_name, sheet_number, user_range) to database
    start the change tracking process in spreadsheets
    """
    user_id = callback_query.message.chat.id
    connection = await db_connection_check(host, user, password)
    user_number = await extraction_query(connection, user_id)
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    commands = ['Добавить таблицу', 'Удалить таблицу', 'Посмотреть таблицы']
    keyboard.add(*commands)

    await bot.send_message(chat_id=user_id, text="Ожидайте изменений...", reply_markup=keyboard)

    async with state.proxy() as data:
        table_name = data['table_name']
        sheet_number = data['sheet_number']
        user_range = data['range']
        interval_value = data['interval_value']

    await insert_new_sheets_info(connection, user_number, table_name, sheet_number, user_range, interval_value)

    cell_values_list = []
    
    async def loop():
        while True:
            conn = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
            cell_values = search_ranges(conn[1], user_range)
            cell_values_list.append(cell_values[1])
            current_range = f"{cell_values[0]['leftcol']}{cell_values[0]['leftrow']}:{cell_values[0]['rightcol']}{cell_values[0]['rightrow']}"

            if len(cell_values_list) == 2:
                range_changes = compare_of_ranges(cell_values_list)
                value_comparison_result = compare_of_values(cell_values_list)
                if range_changes is False:
                    await bot.send_message(chat_id=user_id, text=f"Новый диапазон {current_range}")
                
                if value_comparison_result[0] is not True:
                    for i in value_comparison_result[1]:
                        await bot.send_message(chat_id=user_id, text=f"{i}")

                cell_values_list.pop(0)

            await asyncio.sleep(interval_value)

    asyncio.create_task(loop())

@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def command_handler(message: types.Message):
    """
    function handels a set of commands in replay menu
    """
    user_id = message.chat.id
    connection = await db_connection_check(host, user, password)
    user_number = await extraction_query(connection, user_id)
    user_tables = await tracked_tables(connection, user_number)

    if message.text == 'Добавить таблицу':
        await UserState.table_name.set()
        await bot.send_message(chat_id=message.chat.id, text="Напиши название таблицы")

    elif message.text == 'Удалить таблицу':
        await UserState.tables_manage.set()
        await bot.send_message(chat_id=message.chat.id, text=f"Выберите таблицу из списка и введите ее номер для удаления")

        for rows in user_tables:
            if rows[4] == 'dynamic':
                range = 'Динамический'

            text = f"""Номер: {rows[0]}
Название таблицы: {rows[2]}
Номер листа: {rows[3]}
Диапазон: {range}
Интервал отслеживания: {rows[5]}
"""
            await bot.send_message(chat_id=message.chat.id, text=f"{text}")

    elif message.text == 'Посмотреть все таблицы':
        await bot.send_message(chat_id=message.chat.id, text="Перечень отслеживаемых таблиц")
        
        for rows in user_tables:
            if rows[4] == 'dynamic':
                range = 'Динамический'

            text = f"""Номер: {rows[0]}
Название таблицы: {rows[2]}
Номер листа: {rows[3]}
Диапазон: {range}
Интервал отслеживания: {rows[5]}"""
            
            await bot.send_message(chat_id=message.chat.id, text=f"{text}")
    
@dp.message_handler(state=UserState.tables_manage)
async def manage_table(message: types.Message, state: FSMContext):
    user_id = message.chat.id
    connection = await db_connection_check(host, user, password)
    user_number = await extraction_query(connection, user_id)
    id = int(message.text)
    await delete_spreadsheets(connection, id, user_number)
    await state.finish()

    if delete_spreadsheets is not None:
        await bot.send_message(chat_id=message.chat.id, text="Таблица успешно удалена")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
