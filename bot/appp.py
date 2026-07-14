import re
import telebot
from telebot import types
import sqlite3
import requests
import json
from datetime import datetime
from decouple import config

API_TOKEN = config("API_TOKEN")
ADMIN_BOT_API_TOKEN = config("ADMIN_BOT_API_TOKEN")
ADMIN_BOT_CHAT_ID = config("ADMIN_BOT_CHAT_ID")
API_URL = config("BASE_API_URL")

bot = telebot.TeleBot(API_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_API_TOKEN)


conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    name TEXT,
    phone TEXT,
    code TEXT,
    registration_date TEXT
)
''')
conn.commit()

user_data = {}

def log_event(event):
    print(event)  


def send_data_to_api(user_id, user_data, bot, chat_id):
    try:
        if not API_URL or not API_URL.startswith("http"):
            log_event("❌ Ошибка: Неверный API_URL.")
            bot.send_message(chat_id, "❌ Ошибка сервера. Попробуйте позже.")
            return

        headers = {"Content-Type": "application/json"}
        if API_TOKEN:
            headers["Authorization"] = f"Bearer {API_TOKEN}"

        response = requests.post(API_URL, json=user_data, headers=headers, timeout=10)
        
        if response.status_code == 201:
            bot.send_message(chat_id, "✅ Регистрация успешна!")
            return True
        else:
            error_message = response.json().get("wa_number", ["❌ Ошибка регистрации."])[0]
            bot.send_message(chat_id, f"❌ {error_message}")
            return False

    except requests.exceptions.RequestException as e:
        bot.send_message(chat_id, "❌ Ошибка связи с сервером. Попробуйте позже.")
        log_event(f"Ошибка API: {e}")
 

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = get_user(message.chat.id)
    if not user:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('Регистрация')
        bot.send_message(message.chat.id, "👋 Добро пожаловать! Пожалуйста, зарегистрируйтесь, чтобы продолжить.", reply_markup=markup)
    else:
        send_main_menu(message)


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def send_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('Аккаунт', 'Запрещённые товары','Канал',)
    bot.send_message(message.chat.id, "Выберите нужный раздел:", reply_markup=markup)

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        return {
            'user_id': user[1],
            'name': user[2],
            'phone': user[3],
            'code': user[4],
            'registration_date': user[5]
        }
    return None

@bot.message_handler(func=lambda message: message.text == 'Регистрация')
def registration(message):
    try:
        user = get_user(message.chat.id)
        if user:
            bot.send_message(message.chat.id, "Вы уже зарегистрированы!")
            send_main_menu(message)
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('Отмена')
        msg = bot.send_message(message.chat.id, "Введите ваше имя:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_name_step)
    except Exception as e:
        log_event(f"Ошибка в процессе регистрации: {e}")

def process_name_step(message):
    try:
        if message.text.lower() == 'отмена':
            bot.send_message(message.chat.id, "Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
            return
        user_data[message.chat.id] = {'name': message.text}
        msg = bot.send_message(message.chat.id, "Введите ваш ватсап номер (пример: +996559708005):")
        bot.register_next_step_handler(msg, process_phone_step)
    except Exception as e:
        log_event(f"Ошибка на этапе ввода имени: {e}")

def process_phone_step(message):
    try:
        if message.text.lower() == 'отмена':
            bot.send_message(message.chat.id, "Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
            return
        
        phone = message.text.strip()
        if not re.match(r'^\+\d{10,15}$', phone):
            msg = bot.send_message(message.chat.id, "Неверный формат номера. Введите снова (пример: +996559708005):")
            bot.register_next_step_handler(msg, process_phone_step)
            return

        user_data[message.chat.id]['phone'] = phone
        complete_registration(message)
    except Exception as e:
        log_event(f"Ошибка на этапе ввода телефона: {e}")


def complete_registration(message):
    try:
        user_id = message.chat.id

        if user_id not in user_data:
            bot.send_message(user_id, "⚠ Ошибка: ваши данные не найдены. Попробуйте зарегистрироваться снова.")
            return

        name = user_data[user_id].get('name', 'Не указано')
        phone = user_data[user_id].get('phone', 'Не указан')

        cursor.execute('SELECT code FROM users WHERE user_id = ?', (user_id,))
        existing_user = cursor.fetchone()
        if existing_user:
            bot.send_message(user_id, "✅ Вы уже зарегистрированы!")
            send_main_menu(message)
            return

        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        START_CODE = 2900
        user_code = f"{START_CODE + user_count + 1}"
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        user_data[user_id]['code'] = user_code
        user_data[user_id]['registration_date'] = registration_date

        res = send_data_to_api(user_id, {"id": user_id, "name": name, "code": user_code, "wa_number": phone}, bot, user_id)

        if res:
            cursor.execute('INSERT INTO users (user_id, name, phone, code, registration_date) VALUES (?, ?, ?, ?, ?)',
                       (user_id, name, phone, user_code, registration_date))
            conn.commit()

            send_admin_notification(user_data[user_id])

        

            bot.send_message(user_id, f"✅ *Регистрация завершена!*\n\n"
                                    f"📌 *Ваши данные:*\n"
                                    f"🔹 *Имя:* {name}\n"
                                    f"📞 *Телефон:* {phone}\n"
                                    f"🆔 *Уникальный код:* {user_code}\n"
                                    f"📅 *Дата регистрации:* {registration_date}",
                            parse_mode="Markdown")

            address_message = (
                "杨小姐-(ваш код)\n"
                "18666559560\n"
                "广东省广州市白云区石井街潭村水牛路2号穗新创意园A栋103仓-入仓码RKG-ваш код(ваш номер)имя"
            )
                
            bot.send_message(user_id, address_message, parse_mode="Markdown")

            # Отправка видео-инструкций
            video_paths = ['pinduoduo.mp4', '1688.mp4', 'taobao.mp4']
            for path in video_paths:
                try:
                    with open(path, 'rb') as video:
                        bot.send_video(user_id, video)
                except FileNotFoundError:
                    bot.send_message(user_id, f"⚠ Видео {path} временно недоступно.")

            bot.send_message(user_id, "🎉 Теперь вы можете пользоваться нашим сервисом!")
            send_main_menu(message)

    except sqlite3.Error as db_error:
        bot.send_message(user_id, "❌ Ошибка базы данных. Попробуйте позже.")
        log_event(f"Ошибка БД при регистрации пользователя {user_id}: {db_error}")
    except requests.exceptions.RequestException as api_error:
        bot.send_message(user_id, "⚠ Ошибка соединения с сервером. Данные не отправлены.")
        log_event(f"Ошибка API при регистрации пользователя {user_id}: {api_error}")
    except Exception as e:
        log_event(f"Неизвестная ошибка при регистрации пользователя {user_id}: {e}")

def send_admin_notification(user_data):
    try:
        admin_message = (
            f"🚀 Новый пользователь зарегистрирован:\n"
            f"👤 Имя: {user_data.get('name', 'Не указано')}\n"
            f"📞 Телефон: {user_data.get('wa_number', 'Не указан')}\n"
            f"🔑 Код: {user_data.get('code', 'Не указан')}\n"
            f"📅 Дата регистрации: {user_data.get('registration_date', 'Не указана')}"
        )
        admin_bot.send_message(ADMIN_BOT_CHAT_ID, admin_message)
        log_event("✅ Уведомление администратору отправлено")
    except Exception as e:
        log_event(f"❌ Ошибка отправки уведомления админу: {e}")

@bot.message_handler(func=lambda message: message.text == 'Аккаунт')
def account_info(message):
    try:
        user = get_user(message.chat.id)
        if user:
            bot.send_message(
                message.chat.id,
                f"Ваш аккаунт:\n"
                f"Имя: {user['name']}\n"
                f"Телефон: {user['phone']}\n"
                f"Код: {user['code']}\n"
                f"Дата регистрации: {user['registration_date']}"
            )
        else:
            bot.send_message(message.chat.id, "Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь.")
    except Exception as e:
        log_event(f"Ошибка при получении информации об аккаунте: {e}")



@bot.message_handler(func=lambda message: message.text == 'Канал')
def send_channel_links(message):
    try:
        bot.send_message(
            message.chat.id,
            "Ссылки на наши каналы:\n"
            "Для связи: [(+996 705 901 547)](+996 705 901 547)",
            parse_mode="Markdown"
        )
    except Exception as e:
        log_event(f"Ошибка при отправке ссылок на каналы: {e}")


@bot.message_handler(func=lambda message: message.text == 'Запрещённые товары')
def send_prohibited_items(message):
    try:
        image_paths = [f"{i}.png" for i in range(1, 11)]
        for path in image_paths:
            try:
                with open(path, 'rb') as image:
                    bot.send_photo(message.chat.id, image)
            except FileNotFoundError:
                bot.send_message(message.chat.id, f"Картинка {path} временно недоступна.")
    except Exception as e:
        log_event(f"Ошибка при отправке запрещённых товаров: {e}")


if __name__ == '__main__':
    try:
        bot.infinity_polling()
    except Exception as e:
        log_event(f"Критическая ошибка бота: {e}")
