import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

TOKEN = "8644848473:AAG8tB1x79AopY0hA1zoDShJ4Z1UhNHILKo"
ADMIN_ID = 8008645253  # o'zingizni ID

bot = telebot.TeleBot(TOKEN)

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU").sheet1

user_data = {}

# START
@bot.message_handler(commands=['start'])
def start(message):
    text = """Assalomu alaykum! 😊

Sizning fikringiz biz uchun juda muhim!

Biz supermarketimizni yanada yaxshilash uchun sizning fikringizga muhtojmiz 🙏

Atigi 1 daqiqa vaqt ajrating — va biz siz uchun yanada yaxshiroq xizmat qilamiz.

Boshlaymiz 👇
"""

    bot.send_message(message.chat.id, text)

    bot.send_message(message.chat.id, "Ismingizni yozing:")
    user_data[message.chat.id] = {}
# NAME
@bot.message_handler(func=lambda m: m.chat.id in user_data and "name" not in user_data[m.chat.id])
def get_name(message):
    user_data[message.chat.id]["name"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Raqamni yuborish", request_contact=True)
    markup.add(btn)

    bot.send_message(message.chat.id, "Telefon raqamingizni yuboring:", reply_markup=markup)

# PHONE
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    user_data[message.chat.id]["phone"] = message.contact.phone_number

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Sharq Haqqulobod", "Sharq To'rtko'l")

    bot.send_message(message.chat.id, "Qaysi filialdan foydalandingiz?", reply_markup=markup)

# BRANCH
@bot.message_handler(func=lambda m: m.chat.id in user_data and "branch" not in user_data[m.chat.id])
def get_branch(message):
    user_data[message.chat.id]["branch"] = message.text

    markup = types.InlineKeyboardMarkup()
    for i in range(1, 6):
        markup.add(types.InlineKeyboardButton(f"⭐ {i}", callback_data=f"rate_{i}"))

    bot.send_message(message.chat.id, "Xizmatimizni baholang:", reply_markup=markup)

# RATING
@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def get_rating(call):
    user_data[call.message.chat.id]["rating"] = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, "Nima sababdan bizni tanlaysiz?")

# NEXT STEPS
steps = [
    "reason_choice",
    "purchase_reason",
    "problems",
    "suggestions",
    "competitor_reason",
    "nps",
    "comment"
]

questions = [
    "Xarid qilishingizga nima ta’sir qildi?",
    "Qanday kamchiliklar bor?",
    "Qanday xizmat qo‘shsak yaxshi bo‘ladi?",
    "Boshqa supermarketga ketishingizga nima sabab bo‘ladi?",
    "0 dan 10 gacha baholang (tavsiya qilish)",
    "Nega shunday baho berdingiz?"
]

@bot.message_handler(func=lambda m: m.chat.id in user_data and "rating" in user_data[m.chat.id])
def process_steps(message):
    data = user_data[message.chat.id]

    for step in steps:
        if step not in data:
            data[step] = message.text
            index = steps.index(step)

            if index < len(questions):
                bot.send_message(message.chat.id, questions[index])
            else:
                save_data(message.chat.id)
            return

def save_data(chat_id):
    data = user_data[chat_id]

    sheet.append_row([
        chat_id,
        data.get("name"),
        data.get("phone"),
        data.get("branch"),
        data.get("rating"),
        data.get("reason_choice"),
        data.get("purchase_reason"),
        data.get("problems"),
        data.get("suggestions"),
        data.get("competitor_reason"),
        data.get("nps"),
        data.get("comment"),
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ])

    bot.send_message(chat_id, "Rahmat! Sizning fikringiz biz uchun juda muhim 🙏")

    user_data.pop(chat_id)

bot.polling()