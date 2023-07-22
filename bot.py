import datetime

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from functions import speardsheets_connection_check, search_ranges, compare_of_values, compare_of_ranges
from db_functions import server_connect_check, db_connection_check, create_database, user_id_tables, tg_user_id_list
from db_functions import create_tables, insert_new_users, insert_new_sheets_info, extraction_query, tracked_tables, delete_spreadsheets
from logger import log_error
from config import SERVICE_ACCOUNT_FILE, SCOPES, tg_token, host, port, user, db_name, password

bot = Bot(token=tg_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

def setup_db(db_host: str, db_port: int, db_user: str, db_password: str, db_name: str) -> None:
    """
    database initialization
    """
    connection = server_connect_check(db_host, db_port, db_user, db_password)
    create_database(connection, db_name)
    create_tables(connection, db_name)

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
    try:
        now = datetime.datetime.now()
        user_id = message.from_user.id
        connection = await db_connection_check(host, port, user, password, user_id)
        users_telegram_id = [value[0] for value in await tg_user_id_list(connection)]

        if user_id not in users_telegram_id:
            await insert_new_users(connection, user_id, now)
            text = """Hello, in order to start tracking changes in your Google Spreadsheets, you need to:

    1. Add a service account for reading in the Google Spreadsheets access settings
    googlesheetsaccess@sheetsauto-382306.iam.gserviceaccount.com

    2. Write to the bot the name of the Google Spreadsheets respecting the case

    3. Write sheet number"""
            markup = InlineKeyboardMarkup()
            item = InlineKeyboardButton(
                text="Service account has added", callback_data="account_added")
            markup.add(item)
            await message.answer(text=text, parse_mode=None, reply_markup=markup)

        else:
            markup = InlineKeyboardMarkup()
            item = InlineKeyboardButton(
                text="bup", callback_data="account_added")
            markup.add(item)
            await message.answer(text='Welcome back', parse_mode=None, reply_markup=markup)

    except Exception as ex:
        log_error(f"Respone from start_command: {ex}")

@dp.callback_query_handler(lambda callback_query: callback_query.data in ["account_added", "retry"])
async def account_added_handler(callback_query: types.CallbackQuery):
    """
    the function catches clicking the "Сервис аккаунт добавлен" button and
    prompts you to input the table name, setting the FSM to the UserState.table_name state
    """
    if callback_query.data in ["account_added", "retry"]:
        user_id = callback_query.message.chat.id
        await UserState.table_name.set()
        await bot.send_message(chat_id=user_id, text="Write the name of the Google Spreadsheets")

@dp.message_handler(state=UserState.table_name)
async def enter_table_name(message: types.Message, state: FSMContext):
    """
    the function is called after entering the table name,
    prompts you to enter the sheet number and puts the FSM in the UserState.sheet_number state
    """
    async with state.proxy() as data:
        data['table_name'] = message.text

    await UserState.sheet_number.set()
    await message.answer("Write the sheet number")

@dp.message_handler(state=UserState.sheet_number)
async def enter_sheet_number(message: types.Message, state: FSMContext):
    """
    the function is called after entering the sheet number,
    resets all FSM states and displays a message "Checking the connection with.."
    """
    try:
        user_id = message.chat.id
        try:
            sheet_number = int(message.text)

            async with state.proxy() as data:
                data['sheet_number'] = sheet_number

            await state.reset_state(with_data=False)
            await message.answer("Checking the connection with..")
            await connection_check(user_id, state)

        except ValueError:
            await bot.send_message(chat_id=user_id,
                                text="Sheet number must be an integer, enter again")
            
    except Exception as ex:
        log_error(f"Respone from enter_sheet_number: {ex}")

async def connection_check(user_id, state: FSMContext):
    """
    the function is called after enter_sheet_number(), checks the connection
    with the spreadsheet and offers to re-enter the data if the connection failed
    """
    try:
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']
            conn = await speardsheets_connection_check(
                SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)

        if conn[0]:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Whole Range", callback_data="dynamic"),
                        types.InlineKeyboardButton(
                            text="Fixed range", callback_data="fix"),
                    ]
                ]
            )
            await bot.send_message(chat_id=user_id, text="""&#x2705; Successful connection 

    Choose a tracking type:

    <strong>"Whole Range"</strong> - range will be determined automatically
    and will expand dynamically when new rows or columns are added. 

    <strong>"Fixed range"</strong> - you need to set one ranges

    The range must be of the format
    <strong>For example</strong>: <code>A1:B4, A4:C6</code>""", parse_mode="HTML", reply_markup=keyboard)

        else:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Enter data again", callback_data="retry"),
                    ]
                ]
            )
            await bot.send_message(chat_id=user_id, text="""\u274C Connection error...
    Check the data:

    Table name - {}

    Sheet number - {}""".format(table_name, sheet_number), reply_markup=keyboard)
            
    except Exception as ex:
        log_error(f"Respone from connection_check: {ex}")
    
@dp.callback_query_handler(lambda callback_query: callback_query.data in ["dynamic", "fix"])
async def range_input(callback_query: types.CallbackQuery, state: FSMContext):
    """
    The function is called when the FSM state changes to UserState.range
    after the button is clicked "Whole Range"
    """
    try:
        user_id = callback_query.message.chat.id

        if callback_query.data == 'fix':
            await UserState.range.set()
            await bot.send_message(chat_id=user_id, text="Enter Range")

        elif callback_query.data == 'dynamic':
            await UserState.interval.set()
            async with state.proxy() as data:
                table_name = data['table_name']
                sheet_number = data['sheet_number']

            conn = await speardsheets_connection_check(
                SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
            all_data = await search_ranges(conn[1])

            left = all_data[0]['leftcol'] + str(all_data[0]['leftrow'])
            right = all_data[0]['rightcol'] + str(all_data[0]['rightrow'])
            start_range = left + ":" + right

            async with state.proxy() as data:
                data['range'] = 'dynamic'

            await bot.send_message(chat_id=user_id,
                                text=f"starting range - {start_range}. Set interval in minutes")
    except Exception as ex:
        log_error(f"Respone from range_input: {ex}")

@dp.message_handler(state=UserState.range)
async def range_interval(message: types.Message, state: FSMContext):
    """
    the function intercepts the UserState.range state and the message from the user with the tracking range
    """
    try:
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']

        conn = await speardsheets_connection_check(
            SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
        cell_values = await search_ranges(conn[1], message.text)
        
        if False in cell_values:
            await message.answer("The range must be of the format <code>A1:B4</code>. Enter again", parse_mode="HTML")

        else:
            await UserState.interval.set()
            async with state.proxy() as data:
                data['range'] = message.text

            await message.answer("Set interval in minutes")

    except Exception as ex:
        log_error(f"Respone from range_interval: {ex}")

@dp.message_handler(state=UserState.interval)
async def interavl_input(message: types.Message, state: FSMContext):
    """
    the function intercepts the UserState.interval state and the tracking interval.
    Returns a button that starts the tracking process
    """
    user_id = message.chat.id
    try:
        async with state.proxy() as data:
            data['interval_value'] = int(message.text) * 60

        markup = InlineKeyboardMarkup()
        item = InlineKeyboardButton(
            text="Start tracking", callback_data="starting")
        markup.add(item)

        await state.reset_state(with_data=False)
        await message.answer(f"Ready! Change interval - {message.text} (minut)", parse_mode=None, reply_markup=markup)

    except ValueError:
        await bot.send_message(chat_id=user_id,
                               text="Interval must be an integer, please re-enter")
        
@dp.callback_query_handler(lambda callback_query: callback_query.data == "starting")
async def range_comparison(callback_query: types.CallbackQuery, state: FSMContext):
    """
    funcion creates a menu with 3 commands which help to manage a spreadsheets
    adds all datas about spreadsheets (table_name, sheet_number, user_range) to database
    start the change tracking process in spreadsheets
    """
    try:
        user_id = callback_query.message.chat.id
        connection = await db_connection_check(host, port, user, password, user_id)
        user_number = await extraction_query(connection, user_id)
        
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        commands = ['Add table', 'Delete table']
        keyboard.add(*commands)

        await bot.send_message(chat_id=user_id, text="wait for changes...", reply_markup=keyboard)

        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = data['sheet_number']
            user_range = data['range']
            interval_value = data['interval_value']

        await insert_new_sheets_info(connection, user_number, table_name, sheet_number, user_range, interval_value, user_id)

        cell_values_list = []
        
        async def loop():
            while True:
                conn = await speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
                cell_values = await search_ranges(conn[1], user_range)
                cell_values_list.append(cell_values[1])
                current_range = f"{cell_values[0]['leftcol']}{cell_values[0]['leftrow']}:{cell_values[0]['rightcol']}{cell_values[0]['rightrow']}"

                if len(cell_values_list) == 2:
                    range_changes = await compare_of_ranges(cell_values_list)
                    value_comparison_result = await compare_of_values(cell_values_list)
                    if range_changes is False:
                        await bot.send_message(chat_id=user_id, text=f"New Range {current_range}")
                    
                    if value_comparison_result[0] is not True:
                        for i in value_comparison_result[1]:
                            await bot.send_message(chat_id=user_id, text=f"Table: {table_name}, sheet: {sheet_number}, сell: {i}")

                    cell_values_list.pop(0)

                await asyncio.sleep(interval_value)

        asyncio.create_task(loop())
    
    except Exception as ex:
        log_error(f"Respone from range_comparison: {ex}")
    
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def command_handler(message: types.Message):
    """
    function handels a set of commands in replay menu
    """
    try:
        user_id = message.chat.id
        connection = await db_connection_check(host, port, user, password, user_id)
        user_number = await extraction_query(connection, user_id)
        user_tables = await tracked_tables(connection, user_number)

        if message.text == 'Add table':
            await UserState.table_name.set()
            await bot.send_message(chat_id=message.chat.id, text="Write the name of the table")

        elif message.text == 'Delete table':
            user_tables_id = [value[0] for value in await user_id_tables(connection, user_number)]

            if len(user_tables_id) == 0:
                await bot.send_message(chat_id=message.chat.id, text="List of monitored tables is empty")
            else:
                await UserState.tables_manage.set()
                await bot.send_message(chat_id=message.chat.id, text="Select a table from the list and enter its number to delete")

                for rows in user_tables:
                    if rows[4] == 'dynamic':
                        range = 'dynamic'
                    else:
                        range = rows[4]

                    text = f"""Number: {rows[0]}
    Table name: {rows[2]}
    Sheet number: {rows[3]}
    Range: {range}
    Tracking interval: {rows[5]}
    """
                    await bot.send_message(chat_id=message.chat.id, text=f"{text}")

    except Exception as ex:
        log_error(f"Respone from command_handler: {ex}")
    
@dp.message_handler(state=UserState.tables_manage)
async def manage_table(message: types.Message, state: FSMContext):
    """
    the function handles the logic for deleting user tables
    """
    user_id = message.chat.id
    connection = await db_connection_check(host, port, user, password, user_id)
    user_number = await extraction_query(connection, user_id)
    user_tables_id = [value[0] for value in await user_id_tables(connection, user_number)]
    try:
        table_id = int(message.text)
        if table_id in user_tables_id:
            await delete_spreadsheets(connection, table_id, user_number)
            await bot.send_message(chat_id=message.chat.id, text="Table deleted successfully")
            await state.finish()

        elif table_id not in user_tables_id and user_tables_id != []:
            await bot.send_message(chat_id=message.chat.id, text="You are not tracking tables with this number")
            await state.finish()

        elif len(user_tables_id) == 0:
            await bot.send_message(chat_id=message.chat.id, text="List of monitored tables is empty")
            await state.finish()

    except ValueError:
        await bot.send_message(chat_id=message.chat.id, text="Number must be an integer")

if __name__ == '__main__':
    setup_db(host, port, user, password, db_name)
    executor.start_polling(dp, skip_updates=True)
