import telebot
from telebot import types
from googletrans import Translator
import mysql.connector
import random

db_config = {
    'user': 'root', 
    'password': 'admin', 
    'host': 'localhost',
    'database': 'dictionaryBot',
}

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

API_TOKEN = ''
bot = telebot.TeleBot(API_TOKEN)
translator = Translator()
# Определим возможные языки
languages = {
    '🇷🇺Русский': 'ru',
    '🇬🇧Английский': 'en',
    '🇩🇪Немецкий': 'de'
}

user_language_preferences = {}
user_testing_progress = {}

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_language_preferences[chat_id] = {'src': None, 'dest': None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_button = types.KeyboardButton('/start')
    stop_button = types.KeyboardButton('/stop')
    test_button = types.KeyboardButton('📝Начать тестирование')
    about_button = types.KeyboardButton('🔎О боте')
    markup.add(start_button, stop_button)
    markup.add(test_button, about_button)

    bot.send_message(chat_id, "Добро пожаловать!👋", reply_markup=markup)

    markup = types.InlineKeyboardMarkup()
    for lang in languages:
        markup.add(types.InlineKeyboardButton(text=lang, callback_data=f'src_{languages[lang]}'))
    bot.send_message(chat_id, "Выберите язык исходного текста:", reply_markup=markup)

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = message.chat.id
    if chat_id in user_language_preferences:
        del user_language_preferences[chat_id]
    if chat_id in user_testing_progress:
        del user_testing_progress[chat_id]
    markup = types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "Бот остановлен. Введите /start для запуска.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['📝Начать тестирование', '🔎О боте'])
def handle_custom_buttons(message):
    if message.text == '📝Начать тестирование':
        choose_training_language(message)
    elif message.text == '🔎О боте':
        send_about_message(message)

def send_about_message(message):
    chat_id = message.chat.id
    about_text = (
        "Этот бот предназначен для перевода текстов и проведения языковых тестов.\n\n"
        "Функционал бота:\n"
        "1. Перевод текстов между русским, английским и немецким языками. Выберите с какого языка на какой будете переводить и просто введите слово! Чтобы сменить языки перевода, нажмите /start на клавиатуре.\n"
        "2. Проведение тестов на знание английского и немецкого языков на уровнях от A1 до C2. Выявите свой уровень владения языком проходя тесты!\n\n"
        "Выбирайте необходимые функции с помощью кнопок.")
    bot.send_message(chat_id, about_text)

def choose_training_language(message):
    chat_id = message.chat.id

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text='🇬🇧Английский', callback_data='train_en'))
    markup.add(types.InlineKeyboardButton(text='🇩🇪Немецкий', callback_data='train_de'))

    bot.send_message(chat_id, "Выберите язык для тренировки:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('train_'))
def choose_language_level(call):
    chat_id = call.message.chat.id
    training_language = call.data.split('_')[1]

    user_testing_progress[chat_id] = {'training_language': training_language}

    markup = types.InlineKeyboardMarkup()
    levels = ['⚪A1', '🟢A2', '🟡B1', '🟠B2', '🔴C1', '⚫C2']
    for level in levels:
        markup.add(types.InlineKeyboardButton(text=level, callback_data=f'test_{level}'))
    
    lang = 'английскому' if training_language == 'en' else 'немецкому'
    bot.edit_message_text("Вы выбрали тест по " + lang + "\nВыберите уровень владения языком для тестирования:", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('test_'))
def starting_test(call):
    chat_id = call.message.chat.id
    level = call.data.split('_')[1]
    level = level[1:]

    training_language = user_testing_progress[chat_id]['training_language']
    table_name = f'words_{level}' if training_language == 'en' else f'words_{level}_de'
    column_name = f'word_{level}_en' if training_language == 'en' else f'word_{level}_de'

    # Запрос к базе данных для выбора случайных слов
    cursor.execute(f"SELECT word_{level}_ru, {column_name} FROM {table_name} ORDER BY RAND() LIMIT 5")
    words = cursor.fetchall()

    if chat_id not in user_testing_progress:
        user_testing_progress[chat_id] = {'words': [], 'current_word': 0, 'correct': 0, 'errors': []}
    
    user_testing_progress[chat_id]['words'] = words
    user_testing_progress[chat_id]['current_word'] = 0
    user_testing_progress[chat_id]['correct'] = 0
    user_testing_progress[chat_id]['errors'] = []

    lang = 'английскому' if training_language == 'en' else 'немецкому'

    #bot.send_message(chat_id, "Начинаем тест уровня " + level + " " + lang + " языка")
    bot.edit_message_text("Начинаем тест по " + lang + " уровня " + level, chat_id, call.message.message_id)

    ask_next_word(chat_id)

def ask_next_word(chat_id):
    progress = user_testing_progress[chat_id]
    if progress['current_word'] < len(progress['words']):
        word = progress['words'][progress['current_word']][0]
        bot.send_message(chat_id, f"Переведите слово: {word}")
    else:
        show_results(chat_id)

@bot.message_handler(func=lambda message: message.chat.id in user_testing_progress)
def handle_test_response(message):
    chat_id = message.chat.id
    progress = user_testing_progress[chat_id]
    word, correct_translation = progress['words'][progress['current_word']]
    
    if message.text.strip().lower() in correct_translation.strip().lower():
        progress['correct'] += 1
    else:
        progress['errors'].append((word, correct_translation, message.text.strip()))

    progress['current_word'] += 1
    ask_next_word(chat_id)

def show_results(chat_id):
    progress = user_testing_progress[chat_id]
    total_words = len(progress['words'])
    correct_answers = progress['correct']
    
    result_message = f"Тест завершен!\n\nКоличество правильных ответов: {correct_answers} из {total_words}\n"
    if progress['errors']:
        result_message += "\nОшибки:\n"
        for word, correct_translation, user_translation in progress['errors']:
            result_message += f"Слово: {word}\nПравильный перевод: {correct_translation}\nВаш ответ: {user_translation}\n\n"
    
    if user_language_preferences[chat_id]['src'] == 'ru': sourceLang = 'русского'
    elif user_language_preferences[chat_id]['src'] == 'en': sourceLang = 'английского'
    else: sourceLang = 'немецкого'

    if user_language_preferences[chat_id]['dest'] == 'ru': transLang = 'русский'
    elif user_language_preferences[chat_id]['dest'] == 'en': transLang = 'английский'
    else: transLang = 'немецкий'

    result_message += f"Можете продолжить переводить слова с " + sourceLang + " на " + transLang + " или пройти еще одно тестирование"

    bot.send_message(chat_id, result_message)
    del user_testing_progress[chat_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('src_'))
def set_source_language(call):
    chat_id = call.message.chat.id
    src_lang_code = call.data.split('_')[1]
    user_language_preferences[chat_id]['src'] = src_lang_code

    markup = types.InlineKeyboardMarkup()
    for lang in languages:
        markup.add(types.InlineKeyboardButton(text=lang, callback_data=f'dest_{languages[lang]}'))
    
    if user_language_preferences[chat_id]['src'] == 'ru': sourceLang = 'русского'
    elif user_language_preferences[chat_id]['src'] == 'en': sourceLang = 'английского'
    else: sourceLang = 'немецкого'

    bot.edit_message_text("Вы будете переводить с " + sourceLang + "\nВыберите язык для перевода:", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dest_'))
def set_destination_language(call):
    chat_id = call.message.chat.id
    dest_lang_code = call.data.split('_')[1]
    user_language_preferences[chat_id]['dest'] = dest_lang_code

    if user_language_preferences[chat_id]['src'] == 'ru': sourceLang = 'русского'
    elif user_language_preferences[chat_id]['src'] == 'en': sourceLang = 'английского'
    else: sourceLang = 'немецкого'

    if user_language_preferences[chat_id]['dest'] == 'ru': transLang = 'русский'
    elif user_language_preferences[chat_id]['dest'] == 'en': transLang = 'английский'
    else: transLang = 'немецкий'

    bot.edit_message_text("Отлично! Переводчик настроен для перевода с " + sourceLang + " на " + transLang + ". Теперь отправьте мне текст для перевода.", chat_id, call.message.message_id, reply_markup=None)

@bot.message_handler(func=lambda message: user_language_preferences[message.chat.id]['src'] and user_language_preferences[message.chat.id]['dest'])
def translate_message(message):
    chat_id = message.chat.id
    src_lang = user_language_preferences[chat_id]['src']
    dest_lang = user_language_preferences[chat_id]['dest']

    try:
        translation = translator.translate(message.text, src=src_lang, dest=dest_lang)
        bot.send_message(chat_id, translation.text)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка перевода: {str(e)}")

bot.polling()