import telebot
from telebot import types
import requests
import sqlite3
import schedule
import time
import threading
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from timezonefinder import TimezoneFinder  # Новая библиотека для получения часового пояса
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация бота
bot = telebot.TeleBot('6508339301:AAGj-mTwiPpYnGEAVh2AQnn5BQ7pdIIB6vQ')  # Замените на свой токен
geolocator = Nominatim(user_agent="geoapiExercises")
timezone_finder = TimezoneFinder()  # Инициализация TimezoneFinder

# Подключение к базе данных SQLite
conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        city TEXT,
        timezone TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER,
        task TEXT,
        time TEXT
    )
''')
conn.commit()

# Функция для получения информации о погоде
def get_weather(city):
    api_key = '8418ca95623f7fb933727b8e367e8361'  # Замените на свой ключ API
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Ошибка API: {response.status_code}, {response.text}")
        return None
    return response.json()

# Функция для получения часового пояса по городу
def get_timezone_by_city(city):
    try:
        location = geolocator.geocode(city)
        if location:
            timezone = timezone_finder.timezone_at(lat=location.latitude, lng=location.longitude)
            return timezone
        else:
            return None
    except GeocoderTimedOut:
        return get_timezone_by_city(city)

# Функция для запланированных задач
def scheduled_task():
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    for task in tasks:
        chat_id = task[1]
        task_text = task[2]
        bot.send_message(chat_id, f"Запланированная задача: {task_text}")

# Регистрация пользователя
@bot.message_handler(commands=['start'])
def start_registration(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, укажите ваше имя:")
    bot.register_next_step_handler(message, process_first_name)

def process_first_name(message):
    first_name = message.text
    bot.send_message(message.chat.id, "Введите вашу фамилию:")
    bot.register_next_step_handler(message, lambda m: process_last_name(m, first_name))

def process_last_name(message, first_name):
    last_name = message.text
    bot.send_message(message.chat.id, "Введите ваш город:")
    bot.register_next_step_handler(message, lambda m: process_city(m, first_name, last_name))

def process_city(message, first_name, last_name):
    city = message.text
    timezone = get_timezone_by_city(city)

    if timezone is None:
        bot.send_message(message.chat.id, "Не удалось определить часовой пояс. Попробуйте ввести город еще раз.")
        bot.register_next_step_handler(message, lambda m: process_city(m, first_name, last_name))
        return

    cursor.execute("INSERT OR REPLACE INTO users (chat_id, first_name, last_name, city, timezone) VALUES (?, ?, ?, ?, ?)",
                   (message.chat.id, first_name, last_name, city, timezone))
    conn.commit()

    logging.info(f"Пользователь {first_name} {last_name} зарегистрирован в городе {city} с часовым поясом {timezone}")
    bot.send_message(message.chat.id, f"Регистрация завершена! Привет, {first_name} {last_name} из {city}.")
    show_main_menu(message)

def show_main_menu(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Получить погоду", "Запланировать задачу", "Посмотреть расписание", "Помощь"]
    keyboard.add(*buttons)
    bot.send_message(message.chat.id, "Как я могу помочь?", reply_markup=keyboard)

# Обработчик получения погоды
@bot.message_handler(func=lambda message: message.text == "Получить погоду")
def ask_city_for_weather(message):
    cursor.execute("SELECT city FROM users WHERE chat_id=?", (message.chat.id,))
    result = cursor.fetchone()
    if result:
        city = result[0]
        weather_data = get_weather(city)
        if weather_data is None or weather_data.get('cod') != 200:
            bot.send_message(message.chat.id, "Город не найден. Попробуйте снова.")
            return
        temp = weather_data['main']['temp']
        description = weather_data['weather'][0]['description']
        bot.send_message(message.chat.id, f"Температура в {city}: {temp}°C\nОписание: {description}")
    else:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь, используя команду /start.")

# Обработчик планирования задач
@bot.message_handler(func=lambda message: message.text == "Запланировать задачу")
def ask_for_task(message):
    bot.send_message(message.chat.id, "Введите задачу:")
    bot.register_next_step_handler(message, process_task)

def process_task(message):
    task = message.text
    bot.send_message(message.chat.id, "Введите время для выполнения задачи (например, 15:30):")
    bot.register_next_step_handler(message, lambda m: schedule_task(m, task))

def schedule_task(message, task):
    time = message.text
    cursor.execute("INSERT INTO tasks (chat_id, task, time) VALUES (?, ?, ?)", (message.chat.id, task, time))
    conn.commit()
    bot.send_message(message.chat.id, f"Задача '{task}' запланирована на {time}.")

# Обработчик просмотра расписания
@bot.message_handler(func=lambda message: message.text == "Посмотреть расписание")
def show_schedule(message):
    cursor.execute("SELECT * FROM tasks WHERE chat_id=?", (message.chat.id,))
    tasks = cursor.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "У вас нет запланированных задач.")
    else:
        schedule_message = "\n".join([f"{task[2]} в {task[3]}" for task in tasks])
        bot.send_message(message.chat.id, f"Ваше расписание:\n{schedule_message}")

# Обработчик команды /help
@bot.message_handler(func=lambda message: message.text == "Помощь")
def send_help(message):
    bot.send_message(message.chat.id, "Вы можете:\n- Получить погоду\n- Запланировать задачу\n- Посмотреть расписание")

# Запуск запланированных задач в отдельном потоке
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск бота
if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    bot.polling(none_stop=True)
