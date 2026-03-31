import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU").sheet1

user_data = {}

# START
@bot.message_handler(commands=['start'])
def start(message):
    user_data[message.chat.id] = {}

    bot.send_message(message.chat.id, "Assalomu alaykum! 😊\nIsmingizni yozing:")

# NAME
@bot.message_handler(func=lambda m: m.chat.id in user_data and "name" not in user_data[m.chat.id])
def get_name(message):
    user_data[message.chat.id]["name"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Raqamni yuborish", request_contact=True)
    markup.add(btn)

    bot.send_message(message.chat.id, "Telefon raqamingizni yuboring:", reply_markup=markup)

# CONTACT
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    user_data[message.chat.id]["phone"] = message.contact.phone_number
    bot.send_message(message.chat.id, "Xizmatni 1-5 baholang:")

# MESSAGE FLOW
@bot.message_handler(func=lambda m: m.chat.id in user_data)
def flow(message):
    data = user_data[message.chat.id]

    if "rating" not in data:
        data["rating"] = message.text
        bot.send_message(message.chat.id, "Izoh yozing:")
    else:
        sheet.append_row([
            message.chat.id,
            data.get("name"),
            data.get("phone"),
            data.get("rating"),
            message.text,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ])
        bot.send_message(message.chat.id, "Rahmat 🙏")
        user_data.pop(message.chat.id)

# WEBHOOK
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot ishlayapti!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://feedback-bot-saru.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=10000)