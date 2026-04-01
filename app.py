import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json

# TOKEN
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open_by_key("1ghegwU8QA-JiARIMuFyiBAHyZGDw2238krqNhukzCrU").sheet1

# DATA
user_data = {}

# SAVOLLAR
steps = ["reason", "problems", "suggestions"]

questions = [
    "Bizni tanlashingizga asosiy sabab nima?",
    "Xizmatimizda sizga yoqmagan jihatlar bormi?",
    "Nimalarni yaxshilasak, siz bizdan ko‘proq foydalanar edingiz?"
]

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

# PHONE
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    chat_id = message.chat.id

    # 📱 Telefonni standart ko‘rinishga keltiramiz
    phone = message.contact.phone_number.replace(" ", "").replace("-", "")

    # 🔒 CHECK
    try:
        existing_phone = sheet.findall(phone)
        existing_id = sheet.findall(str(chat_id))

        if existing_phone or existing_id:
            bot.send_message(chat_id, "Siz allaqachon ishtirok etgansiz 🙏")
            user_data.pop(chat_id, None)
            return
    except Exception as e:
        print("Check error:", e)

    # ✅ SAQLASH (ICHIDA BO‘LISHI SHART)
    user_data[chat_id]["phone"] = phone

    # 🎁 SKIDKA
    bot.send_message(chat_id, "🎁 Rahmat! Sizga 2% chegirma berildi")

    bot.send_message(chat_id, "Agar vaqtingiz bo‘lsa, qisqa savollarga javob berib ketsangiz, sizning fikringiz biz uchun juda muhim 🙏")

    # 👉 KEYIN FILIAL
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Haqqulobod", "To‘rtko‘l")

    bot.send_message(chat_id, "Qaysi filialdan foydalandingiz?", reply_markup=markup)
# BRANCH
@bot.message_handler(func=lambda m: m.chat.id in user_data and "branch" not in user_data[m.chat.id])
def get_branch(message):
    user_data[message.chat.id]["branch"] = message.text

    bot.send_message(message.chat.id, questions[0])

# QUESTIONS FLOW
@bot.message_handler(func=lambda m: m.chat.id in user_data and "branch" in user_data[m.chat.id] and "rating" not in user_data[m.chat.id])
def process_steps(message):
    data = user_data[message.chat.id]

    for i, step in enumerate(steps):
        if step not in data:
            data[step] = message.text

            if i == len(steps) - 1:
                # barcha savollar tugadi → rating
                markup = types.InlineKeyboardMarkup()
                for j in range(1, 6):
                    markup.add(types.InlineKeyboardButton(f"⭐ {j}", callback_data=f"rate_{j}"))

                bot.send_message(message.chat.id,
                                 "Xizmatimizni baholang:",
                                 reply_markup=markup)
            else:
                bot.send_message(message.chat.id, questions[i+1])
            return
@bot.message_handler(func=lambda m: m.chat.id in user_data and user_data[m.chat.id].get("waiting_problem"))
def get_low_rating_problem(message):
    chat_id = message.chat.id

    user_data[chat_id]["low_rating_comment"] = message.text
    user_data[chat_id]["waiting_problem"] = False

    save_data(chat_id)

# RATING
@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def get_rating(call):
    chat_id = call.message.chat.id
    rating = int(call.data.split("_")[1])

    user_data[chat_id]["rating"] = rating

    bot.answer_callback_query(call.id)

    if rating <= 2:
        bot.send_message(
            chat_id,
            "❗ Siz past baho berdingiz. Iltimos, muammoni yozing — biz yaxshilaymiz 🙏"
        )
        user_data[chat_id]["waiting_problem"] = True
    else:
        save_data(chat_id)

# SAVE DATA
def save_data(chat_id):
    data = user_data[chat_id]

    sheet.append_row([
        chat_id,
        data.get("name"),
        data.get("phone"),
        data.get("branch"),
        data.get("rating"),
        data.get("reason"),
        data.get("problems"),
        data.get("suggestions"),
        data.get("low_rating_comment"),
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ])

    # faqat RAHMAT qoldiramiz
    bot.send_message(chat_id, "Rahmat! Sizning fikringiz biz uchun juda muhim 🙏")

    user_data.pop(chat_id)
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