import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU").sheet1

user_data = {}

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Raqam yuborish", request_contact=True)
    markup.add(btn)

    bot.send_message(message.chat.id, "Telefon raqamingizni yuboring:", reply_markup=markup)

# ================= PHONE =================
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    chat_id = message.chat.id

    user_data[chat_id] = {
        "phone": message.contact.phone_number
    }

    bot.send_message(chat_id, "Ismingizni yozing:")

    bot.register_next_step_handler(message, get_name)

# ================= NAME =================
def get_name(message):
    chat_id = message.chat.id
    user_data[chat_id]["name"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Filial 1", "Filial 2", "Filial 3")

    bot.send_message(chat_id, "Qaysi filial?", reply_markup=markup)

    bot.register_next_step_handler(message, get_branch)

# ================= BRANCH =================
def get_branch(message):
    chat_id = message.chat.id
    user_data[chat_id]["branch"] = message.text

    bot.send_message(chat_id, "Fikringizni yozing:")

    bot.register_next_step_handler(message, get_feedback)

# ================= FEEDBACK =================
def get_feedback(message):
    chat_id = message.chat.id
    user_data[chat_id]["feedback"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⭐1", "⭐2", "⭐3", "⭐4", "⭐5")

    bot.send_message(chat_id, "Xizmatni baholang:", reply_markup=markup)

    bot.register_next_step_handler(message, get_rating)

# ================= RATING =================
def get_rating(message):
    chat_id = message.chat.id
    user_data[chat_id]["rating"] = message.text

    save_data(chat_id)

# ================= SAVE =================
def save_data(chat_id):
    data = user_data[chat_id]

    sheet.append_row([
        chat_id,
        data.get("phone"),
        data.get("name"),
        data.get("branch"),
        data.get("feedback"),
        data.get("rating"),
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ])

    bot.send_message(chat_id, "Rahmat! Fikringiz qabul qilindi 🙌")

    user_data.pop(chat_id)

# ================= WEBHOOK =================
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
