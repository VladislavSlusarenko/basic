import telebot
import requests
import json
import schedule
import time
from threading import Thread

bot = telebot.TeleBot('6508339301:AAGj-mTwiPpYnGEAVh2AQnn5BQ7pdIIB6vQ')
API = "8418ca95623f7fb933727b8e367e8361"

user_data = {}
tasks = {}

# Регистрация пользователя
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Hello! Please type /register to register.')

@bot.message_handler(commands=['register'])
def register(message):
    bot.send_message(message.chat.id, 'Please enter your first and last name in the format: Firstname Lastname.')
    bot.register_next_step_handler(message, save_user_data)

def save_user_data(message):
    try:
        name, surname = message.text.split()
        user_data[message.chat.id] = {'name': name, 'surname': surname}
        bot.send_message(message.chat.id, f'You are registered! Name: {name}, Surname: {surname}. Now enter your city for weather updates.')
    except ValueError:
        bot.send_message(message.chat.id, 'Please enter both first and last name. Try again with the format: Firstname Lastname.')
        bot.register_next_step_handler(message, save_user_data)

# Получение погоды
@bot.message_handler(content_types=['text'])
def get_weather(message): 
    if message.chat.id not in user_data:
        bot.send_message(message.chat.id, 'Please register first using the /register command.')
        return

    city = message.text.strip().lower()
    res = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API}&units=metric")
    
    if res.status_code != 200:
        bot.send_message(message.chat.id, 'Could not retrieve weather data. Please check the city name.')
        return
    
    data = json.loads(res.text)
    temp = data["main"]["temp"]
    bot.reply_to(message, f'The weather in {city.title()} is now: {temp}°C.')

    # Add image logic based on temperature here
    image_path = "images/cool1.png" if temp < 15 else "images/warm.png"
    
    try:
        with open(image_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo)
    except FileNotFoundError:
        bot.send_message(message.chat.id, 'Image not found.')

# Функционал с заданиями
def send_task():
    for user_id in user_data:
        bot.send_message(user_id, "Your task: Do 10 push-ups!")

def ask_if_done():
    for user_id in user_data:
        bot.send_message(user_id, "Did you complete your task? Reply with Yes or No.")

# Настраиваем расписание
def schedule_jobs():
    schedule.every().hour.do(send_task)
    schedule.every().hour.at(":60").do(ask_if_done)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск планировщика в отдельном потоке
def run_scheduler():
    task_thread = Thread(target=schedule_jobs)
    task_thread.start()

run_scheduler()
bot.polling(none_stop=True)
