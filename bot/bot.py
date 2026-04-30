import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN = os.environ.get("BOT_TOKEN", "")
MINIAPP_URL = os.environ.get("MINIAPP_URL", "")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
if not MINIAPP_URL:
    raise RuntimeError("MINIAPP_URL не задан")

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["start"])
def start(message):
    user = message.from_user
    name = f"@{user.username}" if user.username else user.first_name

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL)))

    bot.send_message(message.chat.id, f"Привет, {name}!", reply_markup=markup)


bot.infinity_polling()
