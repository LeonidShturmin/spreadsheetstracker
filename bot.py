import logging
import pymorphy2
import time

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from functions import speardsheets_connection_check, search_ranges, compare_table_values
from config import tg_token, SERVICE_ACCOUNT_FILE, SCOPES

bot = Bot(token=tg_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
morph = pymorphy2.MorphAnalyzer()

class UserState(StatesGroup):
    """
    the class describes user states
    """
    table_name = State()
    sheet_number = State()
    range = State()
    interval = State()

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """
    Start function with instruction
    """
    user_id = message.from_user.id
    text = """Привет, для того, чтобы начать отслеживать изменения в таблице тебе необходимо:

1. Добавить для чтения сервис аккаунт в настройках доступа таблицы
   googlesheetsaccess@sheetsauto-382306.iam.gserviceaccount.com

3. Написать боту название таблицы в точности соблюдая регистр

4. Перечислить через запятую номера листов для отслеживания. Например: 1, 3, 5"""
    markup = InlineKeyboardMarkup()
    item = InlineKeyboardButton(text="Сервис аккаунт добавлен", callback_data="button_pressed")
    markup.add(item)

    await message.answer(text=text, parse_mode=None, reply_markup=markup)

@dp.callback_query_handler(lambda callback_query: callback_query.data == 'button_pressed')
async def button_pressed_handler(callback_query: types.CallbackQuery):
    """
    the function catches clicking the "Сервис аккаунт добавлен" button and
    prompts you to input the table name, setting the FSM to the UserState.table_name state
    """
    user_id = callback_query.message.chat.id
    await UserState.table_name.set()
    await bot.send_message(chat_id=user_id, text="Отлично, напиши название таблицы")

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
    async with state.proxy() as data:
        data['sheet_number'] = message.text

    await state.reset_state(with_data=False)
    await message.answer("Проверяем соединение с таблицей..")

    user_id = message.chat.id
    await connection_check(user_id, state)

async def connection_check(user_id, state: FSMContext):
    """
    the function is called after enter_sheet_number(), checks the connection
    with the spreadsheet and offers to re-enter the data if the connection failed
    """
    async with state.proxy() as data:
        table_name = data['table_name']
        sheet_number = data['sheet_number']

        try:
            sheet_number = int(sheet_number)

        except ValueError:
            await bot.send_message(chat_id=user_id, text="Номер листа должен быть целым числом")

        connection_consist = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)

    if connection_consist[0]:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="Отслеживать целиком", callback_data="dynamic"),
                    types.InlineKeyboardButton(text="Фиксированный диапазон", callback_data="fix"),
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
                    types.InlineKeyboardButton(text="Ввести данные заново", callback_data="retry"),
                ]
            ]
        )
        await bot.send_message(chat_id=user_id, text="""\u274C Ошибка соединения...
Проверь данные:

Название таблицы - {}

Номер листа - {}""".format(table_name, sheet_number), reply_markup=keyboard)


@dp.callback_query_handler(lambda callback_query: callback_query.data == "retry")
async def retry_data(callback_query: types.CallbackQuery):
    """
    the function is called after pressing the "Ввести данные заново" button puts the FSM
    into the UserState.table_name.set() state and offers to re-enter the data
    """
    user_id = callback_query.message.chat.id
    await UserState.table_name.set()
    await bot.send_message(chat_id=user_id, text="Введите название таблицы")


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
        async with state.proxy() as data:
            table_name = data['table_name']
            sheet_number = int(data['sheet_number'])

        conn = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, sheet_number)
        all_data = search_ranges(conn[1])

        left = all_data[0]['leftcol'] + str(all_data[0]['leftrow'])
        right = all_data[0]['rightcol'] + str(all_data[0]['rightrow'])

        start_range = left + ":" + right

        await bot.send_message(chat_id=user_id, text=f"Стартовый диапазон - {start_range}")

@dp.message_handler(state=UserState.range)
async def range_interavl(message: types.Message, state: FSMContext):
    """
    afdsfdsfsd
    """
    await UserState.interval.set()
    async with state.proxy() as data:
        data['range'] = message.text
        
    await message.answer("Осталось определить интервал обновлений в минутах")

@dp.message_handler(state=UserState.interval)
async def interavl_input(message: types.Message, state: FSMContext):
    """
    sdfdsfdsfds
    """
    async with state.proxy() as data:
        data['interval'] = message.text
        table_name = data['table_name']
        sheet_number = data['sheet_number']
        user_range = data['range']
        interval = data['interval']

    markup = InlineKeyboardMarkup()
    item = InlineKeyboardButton(text="Начать отслеживание", callback_data="starting")
    markup.add(item)

    await state.reset_state(with_data=False)
    await message.answer(f"Готово! Интервал изменений - {interval} (минут)", parse_mode=None, reply_markup=markup)



@dp.callback_query_handler(lambda callback_query: callback_query.data == "starting")
async def some_function(callback_query: types.CallbackQuery, state: FSMContext):
    """
    """
    user_id = callback_query.message.chat.id
    await bot.send_message(chat_id=user_id, text="Ожидайте изменений")

    async with state.proxy() as data:
        table_name = data['table_name']
        sheet_number = data['sheet_number']
        user_range = data['range']
        interval = data['interval']

    cell_values_list = []

    async def loop():
        while True:
            connection_consist = speardsheets_connection_check(SERVICE_ACCOUNT_FILE, SCOPES, table_name, int(sheet_number))
            cell_values = search_ranges(connection_consist[1], user_range)
            cell_values_list.append(cell_values[1])

            if len(cell_values_list) == 2:
                value_comparison_result = compare_table_values(cell_values_list)

                print(value_comparison_result)
                cell_values_list.pop(0) 

            await asyncio.sleep(int(interval))

    asyncio.create_task(loop())

if __name__ == '__main__':
    executor.start_polling(dp)
