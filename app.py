
import telebot
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from telebot import types
import os
import json
from openai import OpenAI

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

user_data = {}

# ================= MENU =================
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎁 Skidkani tekshirish", "📝 Fikr qoldirish ")
    markup.add("📸 Instagram", "📢 Telegram")

    bot.send_message(chat_id, "Kerakli bo‘limni tanlang 👇", reply_markup=markup)

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    try:
        result = sheet.findall(str(chat_id))

        if result:
            main_menu(chat_id)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn = types.KeyboardButton("📞 Raqamni yuborish", request_contact=True)
            markup.add(btn)

            bot.send_message(chat_id, "Telefon raqamingizni yuboring:", reply_markup=markup)

    except:
        bot.send_message(chat_id, "Xatolik yuz berdi")

# ================= PHONE =================
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    chat_id = message.chat.id
    phone = message.contact.phone_number.replace(" ", "").replace("-", "")

    try:
        existing = sheet.findall(phone)

        if existing:
            bot.send_message(chat_id, "Siz allaqachon skidka olgansiz 🎁")
            main_menu(chat_id)
            return
    except:
        pass

    user_data[chat_id] = {"phone": phone}

    bot.send_message(chat_id, "🎁 Sizga 2% chegirma berildi!")

    bot.send_message(chat_id,
                     "Agar vaqtingiz bo‘lsa, qisqa savollarga javob berib ketsangiz, sizning fikringiz biz uchun juda muhim 🙏")

    bot.send_message(chat_id, "Ismingizni yozing:")

# ================= FEEDBACK =================
@bot.message_handler(func=lambda m: m.chat.id in user_data and "name" not in user_data[m.chat.id])
def get_name(message):
    user_data[message.chat.id]["name"] = message.text

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Haqqulobod", "To‘rtko‘l")

    bot.send_message(message.chat.id, "Qaysi filialdan foydalandingiz?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in user_data and "branch" not in user_data[m.chat.id])
def get_branch(message):
    user_data[message.chat.id]["branch"] = message.text
    bot.send_message(message.chat.id, "Bizni tanlashingizga asosiy sabab nima?")

steps = ["reason", "problems", "suggestions"]

questions = [
    "Xizmatimizda sizga yoqmagan jihatlar bormi?",
    "Nimalarni yaxshilasak, siz bizdan ko‘proq foydalanar edingiz?"
]

@bot.message_handler(func=lambda m: m.chat.id in user_data and "branch" in user_data[m.chat.id] and "rating" not in user_data[m.chat.id])
def process_steps(message):
    data = user_data[message.chat.id]

    if "reason" not in data:
        data["reason"] = message.text
        bot.send_message(message.chat.id, questions[0])
    elif "problems" not in data:
        data["problems"] = message.text
        bot.send_message(message.chat.id, questions[1])
    elif "suggestions" not in data:
        data["suggestions"] = message.text

        markup = types.InlineKeyboardMarkup()
        for i in range(1, 6):
            markup.add(types.InlineKeyboardButton(f"⭐ {i}", callback_data=f"rate_{i}"))

        bot.send_message(message.chat.id, "Xizmatimizni baholang:", reply_markup=markup)

# ================= LOW RATING =================
@bot.message_handler(func=lambda m: m.chat.id in user_data and user_data[m.chat.id].get("waiting_problem"))
def low_rating(message):
    chat_id = message.chat.id
    user_data[chat_id]["low_rating_comment"] = message.text
    user_data[chat_id]["waiting_problem"] = False
    save_data(chat_id)

# ================= RATING =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def get_rating(call):
    chat_id = call.message.chat.id
    rating = int(call.data.split("_")[1])

    user_data[chat_id]["rating"] = rating
    bot.answer_callback_query(call.id)

    if rating <= 2:
        bot.send_message(chat_id, "❗ Muammoni yozing:")
        user_data[chat_id]["waiting_problem"] = True
    else:
        save_data(chat_id)

def analyze_feedback(data):
    user_text = f"""
    Name: {data.get("name")}
    Branch: {data.get("branch")}
    Reason: {data.get("reason")}
    Problems: {data.get("problems")}
    Suggestions: {data.get("suggestions")}
    Rating: {data.get("rating")}
    """

    response = client_ai.chat.completions.create(
        model="gpt-5.3",
        messages=[
            {"role": "system", "content": """
You are an AI Business Analyst and CRM Manager for a supermarket.

Analyze customer feedback and return JSON:
response_to_customer, sentiment, issue, root_cause,
business_recommendations, crm_action, customer_segment, priority_level
"""},
            {"role": "user", "content": user_text}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

# ================= SAVE =================
def save_data(chat_id):
    data = user_data[chat_id]

    try:
        ai_result = analyze_feedback(data)
        parsed = json.loads(ai_result)
    except:
        parsed = {}

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
        datetime.now().strftime("%Y-%m-%d %H:%M"),

        # AI DATA
        parsed.get("sentiment"),
        parsed.get("issue"),
        parsed.get("root_cause"),
        parsed.get("customer_segment"),
        parsed.get("priority_level"),
        parsed.get("crm_action")
    ])

    if parsed.get("response_to_customer"):
        bot.send_message(chat_id, parsed.get("response_to_customer"))

    bot.send_message(chat_id, "Rahmat! 🙏")
    user_data.pop(chat_id)
    main_menu(chat_id)
# ================= MENU BUTTONS =================
@bot.message_handler(func=lambda m: m.text == "🎁 Skidkani tekshirish")
def check_discount(message):
    chat_id = message.chat.id

    try:
        result = sheet.findall(str(chat_id))
        if result:
            bot.send_message(chat_id, "✅ Siz skidkadan foydalangansiz")
        else:
            bot.send_message(chat_id, "❌ Siz hali skidka olmadingiz")
    except:
        bot.send_message(chat_id, "Xatolik yuz berdi")

@bot.message_handler(func=lambda m: m.text == "📝 Fikr qoldirish")
def feedback_menu(message):
    user_data[message.chat.id] = {}
    bot.send_message(message.chat.id, "Ismingizni yozing:")

@bot.message_handler(func=lambda m: m.text == "📸 Instagram")
def instagram(message):
    bot.send_message(message.chat.id, "https://instagram.com/sharq.supermarketi")

@bot.message_handler(func=lambda m: m.text == "📢 Telegram")
def telegram(message):
    bot.send_message(message.chat.id, "https://t.me/sharqsupermarketi")

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
