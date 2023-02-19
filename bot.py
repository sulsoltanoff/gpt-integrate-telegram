import os
import threading
import time

import telebot
import openai
import logging
import sqlite3
import atexit

# OpenAI API authorisation data
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Creating TG bot
bot = telebot.TeleBot(os.getenv("TG_API_KEY"))

# Create logger for bot
logging.basicConfig(filename='bot.log', level=logging.INFO)

# List of user IDs that are allowed access
ALLOWED_USERS = os.getenv("ALLOWED_USERS").split(",")
ALLOWED_USERS = list(map(int, ALLOWED_USERS))

# Mutex
lock = threading.Lock()

# Time interval for rate limiting
RATE_LIMIT_INTERVAL = 30 * 60  # 30 min

# Last request time
last_request_time = time.time()


# Decorator function to check access
def restricted_access(func):
    def wrapper(message):
        user_id = message.from_user.id
        if user_id in ALLOWED_USERS:
            return func(message)
        else:
            bot.reply_to(message, "You do not have access to this bot.")

    return wrapper


# Create a local variable for each thread
thread_local = threading.local()


# Create a function to retrieve the database connection object for the current thread
def get_conn():
    if not hasattr(thread_local, "conn"):
        thread_local.conn = sqlite3.connect('context.db')
    return thread_local.conn


# Create a table to store the query context
with get_conn() as conn:
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS context
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)''')
    conn.commit()

# Creating a hot cache to store query context
HOT_CACHE_DURATION = 5 * 60  # 5 min
hot_cache = {}


# The /start command handler and refresh the hot cache when the bot starts
@bot.message_handler(commands=['start'])
@restricted_access
def start(message):
    bot.reply_to(message, "Hi, I'm your helper, ready to work with the OpenAI API!")
    user_id = message.from_user.id
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT text FROM context WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
        row = c.fetchone()
        if row is not None:
            hot_cache[user_id] = (row[0], time.time())


# User message handler
@bot.message_handler(func=lambda message: message.text is not None and '/' not in message.text)
@restricted_access
def echo_message(message):
    try:
        text = message.text
        user_id = message.from_user.id

        # Check if the user has sent too many messages in a short period of time
        global last_request_time

        if time.time() - last_request_time < RATE_LIMIT_INTERVAL:
            # Retrieve the last saved request context for a given user from the hot cache
            prev_text, prev_time = hot_cache.get(user_id, (None, 0))

            # If the entry is in the cache and the time to send the request does not exceed 5 minutes, use it as
            # previous context
            if prev_text and time.time() - prev_time < HOT_CACHE_DURATION:
                prompt = prev_text + '\n' + text
            else:
                # Otherwise query the database to get the last query context for this user
                with get_conn() as conn:
                    c = conn.cursor()
                    c.execute("SELECT text FROM context WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
                    row = c.fetchone()
                    prompt = row[0] + '\n' + text if row is not None else text

                    # Refreshing the hot cache
                    hot_cache[user_id] = (prompt, time.time())

        bot.reply_to(message, "Request accepted for processing, please wait.")

        # Generating a response using the OpenAI API
        response = response_to_gpt(prompt)

        # Replying to the user
        bot.reply_to(message, response.choices[0].text)

        # Save the query context to the database
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO context (user_id, text) VALUES (?, ?)", (user_id, text))
            conn.commit()

    except Exception as e:
        logging.error(str(e))
        bot.reply_to(message, f"An error occurred while processing the request. Please try again later. \n {e}")


def response_to_gpt(message):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=message,
        max_tokens=4000,
        temperature=0.7,

    )
    return response


# Add a /help command handler
@bot.message_handler(commands=['help'])
@restricted_access
def help_message(message):
    bot.reply_to(message,
                 "I know how to answer questions using the OpenAI API. Just write me a message and I will try to do it."
                 "Source code for this bot https://github.com/sulsoltanoff/gpt-integrate-telegram")


# Add a function to be called on exit to close the database connection
def close_conn():
    conn = getattr(thread_local, "conn", None)
    if conn is not None:
        conn.close()


# Register a function to be called on exit
atexit.register(conn.close)

if __name__ == "__main__":
    bot.polling(none_stop=True)
