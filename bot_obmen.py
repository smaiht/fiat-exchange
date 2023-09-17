import requests, json, math
from datetime import datetime, timedelta

from config import TOKEN

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ForceReply

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from aiogram.contrib.fsm_storage.memory import MemoryStorage

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


bat = "฿"
rub = "₽"
manager = "rusbat_obmen"
order_group = -1001984281231
stats_group = -1001954374416


# Парсим бинанс
def get_rate(fiat):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "123",
        "content-type": "application/json",
        "Host": "p2p.binance.com",
        "Origin": "https://p2p.binance.com",
        "Pragma": "no-cache",
        "TE": "Trailers",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0"
    }

    data = {
        "asset": "USDT",
        "fiat": fiat,
        "merchantCheck": False,
        "page": 1,
        "payTypes": ["TinkoffNew", "RaiffeisenBank", "HomeCreditBank"] if fiat == "RUB" else None,
        "publisherType": None,
        "rows": 9,
        "tradeType": "BUY" if fiat == "RUB" else "SELL"
    }

    r = requests.post(
        'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search', 
        headers=headers, 
        json=data
    )
    # formatted_json = json.dumps(json.loads(str(r.text)), indent=2)
    # print(result["data"][0]["adv"]["price"])
    result = r.json()
    print(result)
    prices = [adv['adv']['price'] for adv in result['data']]
    return float( result["data"][len(result['data'])-1]["adv"]["price"] ) # достаем последний прайс (последнее = rows-1)



##############################################################################################
# Парсим бинанс и считаем курс и готовим шаблон сообщений
def kurs():
    rub2usdt = get_rate("RUB")
    usdt2bat = get_rate("THB")

    comi = 0
    my_kurs_raw = (rub2usdt / usdt2bat)*(1+comi/100)

    bat2rub = math.ceil(my_kurs_raw * 1000) / 1000
    rub2bat = math.ceil(1/my_kurs_raw * 1000) / 1000

    text = f'/kurs\nАктуальный курс {(datetime.now()+timedelta(hours=4)).strftime("%d.%m.%Y — %H:%M")}:\n\n🇹🇭1 THB = {bat2rub} RUB\n🇷🇺1 RUB = {rub2bat} THB\n\n'

    return bat2rub, rub2bat, text


##############################################################################################
# Шаблон маркапа главного меню
async def main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton(text=f"Обновить курс", callback_data=f"cancel"))
    markup.row(InlineKeyboardButton(text=f"🟢Рассчитать и забронировать онлайн", callback_data=f"calc"))
    markup.row(
        InlineKeyboardButton(text=f"Правила", callback_data='rules'),
        InlineKeyboardButton(text=f"Менеджер", url=f'https://t.me/{manager}')
    )

    bat2rub, rub2bat, text = kurs()

    await bot.send_message(
        chat_id = chat_id,
        text = text+"Введите сумму, чтобы посчитать итого.",
        reply_markup=markup,
        parse_mode = "HTML"
    )

##############################################################################################
# Шаблон отправки статистики
async def statistics(message, name):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row( InlineKeyboardButton(text=f"Написать", url=f"tg://user?id={message.chat.id}")    )
    await bot.send_message(
        chat_id = stats_group, 
        text = f"{message.chat.id}: <b>{name}</b> | @{message.chat.username}",
        reply_markup = markup,
        parse_mode = "HTML"
    )

##############################################################################################
# Обработчик команды /start
@dp.message_handler(commands=['start']) # chat_type=[types.ChatType.PRIVATE])
async def first_meeting(message: types.Message):
    await main_menu(message.chat.id)

    # отсылаем уведомление в телеграме
    await statistics(message, "/start")

    
    with open('rusbat_users.txt', 'a') as file:
        file.write(f'{message.from_user.id}\n')

##############################################################################################
# Обработчик команды /kurs
@dp.message_handler(commands=['kurs', 'menu', 'bot']) # chat_type=[types.ChatType.PRIVATE])
async def rates(message: types.Message):
    await main_menu(message.chat.id)

    # отсылаем уведомление в телеграме
    await statistics(message, "/kurs")
    

##############################################################################################
# Обработчик команды отмены - возврат в главное меню
@dp.callback_query_handler(lambda c: c.data == 'cancel')
async def process_callback_cancel(callback_query: types.CallbackQuery):
    await main_menu(callback_query.message.chat.id)
    await bot.answer_callback_query(callback_query.id)

    # отсылаем уведомление в телеграме
    await statistics(callback_query.message, "'cancel/refresh'")



##############################################################################################
# Обработчик калькулятора - ForceReply()
@dp.callback_query_handler(lambda c: c.data == 'calc')
async def process_callback_calc(callback_query: types.CallbackQuery):
    bat2rub, rub2bat, text = kurs()

    await bot.send_message(
        chat_id = callback_query.message.chat.id,
        text = text+"<b>Введите количество рублей, которое хотите обменять:</b>",
        reply_markup = ForceReply(),
        parse_mode = "HTML"
    )
    await bot.answer_callback_query(callback_query.id)

    # отсылаем уведомление в телеграме
    await statistics(callback_query.message, "'калькулятор суммы'")




##############################################################################################

# Выбрал сумму, перейти дальше к выбору времени. А еще нужно будет в конце сделать расчёт по запросу чтобы пользователю тоже пришло уведомление о сумме, а потом через полчаса уведомление спасибо что воспользовались, ждём вас в гости
@dp.callback_query_handler(lambda c: c.data.startswith('checkout'))
async def checkout(callback_query: types.CallbackQuery):
    # Получаем информацию о товаре из колбака
    data = callback_query.data.split(':')
    rub_receiving = data[1]
    bat_giving = data[2]


    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(InlineKeyboardButton(text=f"Как можно скорее", callback_data=f"time:ASAP:{rub_receiving}:{bat_giving}"))
    markup.row(
        # InlineKeyboardButton(text=f"Через час", callback_data=f"time:hour:{rub_receiving}:{bat_giving}"),
        # InlineKeyboardButton(text=f"В течение дня", callback_data=f"time:today:{rub_receiving}:{bat_giving}"),
        InlineKeyboardButton(text=f"Другое время", callback_data=f"time:other:{rub_receiving}:{bat_giving}")
    )
    markup.row(
        InlineKeyboardButton(text=f"Правила", callback_data='rules'),
        InlineKeyboardButton(text=f"Менеджер", url=f'https://t.me/{manager}'),
        InlineKeyboardButton(text=f"Отменить", callback_data='cancel')
    )

    await bot.send_message(
        chat_id = callback_query.message.chat.id, 
        #reply_to_message_id = callback_query.message.message_id,
        text = f"<b>Информация об обмене:</b>\n\nВы отдаёте: {rub_receiving} рублей🇷🇺\nВы получаете: {bat_giving} бат🇹🇭\n\n<b>Теперь выберите время: </b>",
        reply_markup = markup,
        parse_mode = "HTML"
    )
    # Отвечаем на колбек
    await bot.answer_callback_query(callback_query.id, text = "Выберите время")

    # отсылаем уведомление в телеграме
    await statistics(callback_query.message, f"начало оформления заявки: {rub_receiving} рублей ({bat_giving} бат)")


##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################

class FormStates(StatesGroup):
    SET_PHONE = State()
    SET_ADDRESS = State()


##############################################################################################

# Выбрал time. А еще нужно будет в конце сделать расчёт по запросу чтобы пользователю тоже пришло уведомление о сумме, а потом через полчаса уведомление спасибо что воспользовались, ждём вас в гости
@dp.callback_query_handler(lambda c: c.data.startswith('time'))
async def process_callback_set_address(callback_query: types.CallbackQuery, state: FSMContext):
    await FormStates.SET_ADDRESS.set()

    data = callback_query.data.split(':')
    when_time = "Время: Как можно скорее\n\n" if data[1] == "ASAP" else "" 

    when1 = "<b>В ответном сообщении укажите:</b>\n\n"
    when2 = "<b>🏠Адрес или название отеля/кондо, или ссылку на карты https://goo.gl/maps/wxoTuWXufwdrGr6o9 </b>\n\n"
    
    when3 = "А также\n<b>🗒Любые детали или вопросы.</b>" if data[1] == "ASAP" else "А также\n<b>⏰Время (и любые детали или вопросы).</b>"

    rub_receiving = data[2]
    bat_giving = data[3]

    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(
        InlineKeyboardButton(text=f"Правила", callback_data='rules'),
        InlineKeyboardButton(text=f"Менеджер", url=f'https://t.me/{manager}'),
        InlineKeyboardButton(text=f"Отменить", callback_data='cancel')
    )

    await bot.send_message(
        chat_id = callback_query.message.chat.id, 
        #reply_to_message_id = callback_query.message.message_id,
        text = f"<b>Информация об обмене:</b>\n\nВы отдаёте: {rub_receiving} рублей🇷🇺\nВы получаете: {bat_giving} бат🇹🇭\n\n{when_time}{when1}{when2}{when3}",
        reply_markup = ForceReply(),
        parse_mode = "HTML"
    )
    # Отвечаем на колбек
    await bot.answer_callback_query(callback_query.id, text = "Введите адрес")

    # отсылаем уведомление в телеграме
    await statistics(callback_query.message, f"Указал вермя {when_time}, открыл ввод адреса")

##############################################################################################
##############################################################################################
##############################################################################################
# SET_ADDRESS
@dp.message_handler(state=FormStates.SET_ADDRESS)
async def process_address(message: types.Message, state: FSMContext):
    # print(json.dumps(json.loads(str(message)), indent=4))
    address = str(message.text)

    await state.reset_state()

    info = message.reply_to_message.text.split('В ответном сообщении укажите')[0]+"Адрес: "+address

    await bot.send_message(
        chat_id = message.chat.id, 
        text = f"<b>✅Заявка успешно оформлена✅</b>\n\nОжидайте, наш менеджер @{manager} свяжется с вами при необходимости.\n\n"+info+"\n\nДля оформления новой заявки введите /kurs",
        parse_mode = "HTML"
    )

    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(
        InlineKeyboardButton(text=f"Написать", url=f"tg://user?id={message.from_user.id}"),
        InlineKeyboardButton(text=f"Пингануть", callback_data='ping'),
        InlineKeyboardButton(text=f"Спасибо", callback_data='thx')
    )
    await bot.send_message(
        chat_id = order_group,
        text = f"<b>НОВЫЙ ЗАКАЗ! from @{message.from_user.username} id: {message.from_user.id}</b>\n\n"+info,
        parse_mode = "HTML",
        reply_markup = markup
    )
    # отсылаем уведомление в телеграме
    await statistics(message, f"ввел адрес и оформил заказ: {address}")
##############################################################################################



# PS C:\Users\evgeniy\Desktop\obmexch> & C:/Users/evgeniy/AppData/Local/Microsoft/WindowsApps/python3.11.exe c:/Users/evgeniy/Desktop/obmexch/obmentest.py
# Updates were skipped successfully.
# hello hi we are online
# Task exception was never retrieved
# future: <Task finished name='Task-72' coro=<Dispatcher._process_polling_updates() done, defined at C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\dispatcher.py:407> exception=AttributeError("'NoneType' object has no attribute 'text'")>
# Traceback (most recent call last):
#   File "C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\dispatcher.py", line 415, in _process_polling_updates
#     for responses in itertools.chain.from_iterable(await self.process_updates(updates, fast)):
#                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\dispatcher.py", line 235, in process_updates
#     return await asyncio.gather(*tasks)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\handler.py", line 117, in notify
#     response = await handler_obj.handler(*args, **partial_data)
#                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\dispatcher.py", line 256, in process_update
#     return await self.message_handlers.notify(update.message)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\evgeniy\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\aiogram\dispatcher\handler.py", line 117, in notify
#     response = await handler_obj.handler(*args, **partial_data)
#                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "c:\Users\evgeniy\Desktop\obmexch\obmentest.py", line 273, in process_address
#     info = message.reply_to_message.text.split('Теперь укажите адрес')[0]+"Адрес: "+address
#            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# AttributeError: 'NoneType' object has no attribute 'text'









##############################################################################################
# Обработчик введенной суммы суммы ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
@dp.message_handler(chat_type=[types.ChatType.PRIVATE])
async def exchanges(message: types.Message):
    # print(json.dumps(json.loads(str(message)), indent=4))
    # Сначала выполнить проверку на админ: 
        # Если это админ, то выполнить проверку что за команда, например //admin

    digits = ''.join(filter(lambda character: character.isdigit(), message.text or message.caption))

    bat2rub, rub2bat, text = kurs()
    m_text = "Неправильно введена сумма!\nВведите сумму, чтобы посчитать итого.\n\n"+text

    markup = InlineKeyboardMarkup(row_width=2) # изменить на обратно в корзину

    if digits:
        digit_bat = int(int(digits)*rub2bat)
        # digit_rub = int(int(digits)*bat2rub)
        m_text = text+f"Ваш расчёт:\n\nВы даёте {digits} рублей, а получаете {digit_bat} бат\n\n<b>❗️Подтвердите выбор по кнопке, чтобы продолжить оформление заявки.</b> Либо напишите менеджеру @{manager}"

        markup.row(InlineKeyboardButton(text=f"✅Даю {digits} {rub}, получаю {digit_bat} {bat}", callback_data=f"checkout:{digits}:{digit_bat}"))
        # markup.row(InlineKeyboardButton(text=f"2️⃣Даю {digit_rub} {rub}, получаю {digits} {bat}", callback_data=f"checkout:{digit_rub}:{digits}"))


    markup.row(
        InlineKeyboardButton(text=f"Правила", callback_data='rules'),
        InlineKeyboardButton(text=f"Менеджер", url=f'https://t.me/{manager}'),
        InlineKeyboardButton(text=f"Отменить", callback_data='cancel')
    )
    await message.reply(
        text = m_text,
        reply_markup=markup,
        parse_mode = "HTML"
    )


    # отсылаем уведомление в телеграме
    await statistics(message, f"ввод суммы: {message.text or message.caption}")

##############################################################################################

##############################################################################################
# RULES
@dp.callback_query_handler(lambda c: c.data == 'rules')
async def process_callback_rules(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id, "1. Бесплатная доставка наличных по городу от 30 минут\n\n2. Если вы рядом в районе Пратамнак, то еще быстрее\n\n3. Курс и конечная сумма считаются на месте во время обмена.", show_alert=True)
















# rub2usdt = get_rate("RUB")
# usdt2bat = get_rate("THB")
# suma = 50000
# for i in range(10):
#     kurs = rub2usdt / usdt2bat * (1+i/100)
#     print(f"""{i}% комиссия: Если продать {suma} бат по курсу {kurs}, то получится {suma*kurs} рублей, PROFIT={suma*kurs-suma*rub2usdt / usdt2bat}""")




# Function that runs on startup
async def on_start(_):
    print("hello hi we are online")

# Main function
if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_start, skip_updates=True)