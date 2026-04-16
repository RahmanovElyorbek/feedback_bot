Uimport telebot
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
    markup.add("🎁 Skidkani tekshirish", "📝 Fikr qoldirish")
    bot.send_message(chat_id, "Kerakli bo‘limni tanlang 👇", reply_markup=markup)

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Raqamni yuborish", request_contact=True)
    markup.add(btn)

    bot.send_message(chat_id, "Telefon raqamingizni yuboring:", reply_markup=markup)

# ================= PHONE =================
@bot.message_handler(content_types=['contact'])
def get_phone(message):
    chat_id = message.chat.id
    phone = message.contact.phone_number

    user_data[chat_id] = {
        "phone": phone,
        "messages": []
    }

    bot.send_message(chat_id, "🎁 Sizga 2% chegirma berildi!")

    bot.send_message(chat_id,
        "🤖 Salom! Men Sharq AI man.\n\nBizning supermarketimiz haqida o‘z fikrlaringizni yozing. Siz bilan suhbatlashib, xizmatimizni yaxshilaymiz 🙌")

# ================= AI FUNCTION =================
def analyze_feedback(history):
    is_first = len(history) == 1

    
    response = client_ai.chat.completions.create(
        model="gpt-4.1-mini",
        
prompt = f"""
You are Sharq AI - supermarket yordamchisi.

Conversation:
{history}

First message: {is_first}

Rules:
- Faqat ozbek tilida yoz
- Juda qisqa yoz (maks 10-12 soz)
- 1 gap + 1 savol yoz
- Oddiy insondek gapir
- Rasmiy gaplar yozma

Greeting:
- Agar First message = True bolsa Salom bilan boshlagin
- Aks holda Salom yozma

Understanding:
- User javob bergan bolsa takrorlama
- Oldingi gapga mos javob ber

Flow:
- Agar user aniq gapirsa chuqurlashtir
- Agar umumiy gapirsa aniqlashtir

Examples:
User: non bolimida
AI: tushundim 👍 bu tez-tez boladimi?

User: ishdan keyin
AI: tushundim 👍 osha payt nechta kassa ishlaydi?

IMPORTANT:
- Har doim yangi savol ber
- Bir xil savolni qaytarmagin

Javob ber:
"""
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content
# ================= AI CHAT =================
@bot.message_handler(func=lambda message: message.chat.id in user_data)
def ai_chat(message):
    chat_id = message.chat.id
    text = message.text

    user_data[chat_id]["messages"].append(text)

    try:
        ai_result = analyze_feedback(user_data[chat_id]["messages"])
        reply = ai_result.strip()
        print("AI RESULT:", ai_result)
    except Exception as e:
        print("AI ERROR:", e)
        reply = "Rahmat fikringiz uchun!"

    bot.send_message(chat_id, reply)

    # 🔥 AI tugatdi
    if "tushundim" in reply.lower():
        save_data(chat_id)
        return

    # 🔥 backup
    if len(user_data[chat_id]["messages"]) >= 6 or "tamom" in text.lower():
        save_data(chat_id)
# ================= SAVE =================
def save_data(chat_id):
    data = user_data[chat_id]

    messages = data.get("messages", [])

    row = [
        chat_id,
        data.get("phone"),
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ]

    row.extend(messages)

    sheet.append_row(row)

    bot.send_message(chat_id, "Yozib oldim 👍 Rahmat!")
    user_data.pop(chat_id)
    main_menu(chat_id)
# ================= MENU =================
@bot.message_handler(func=lambda m: m.text == "🎁 Skidkani tekshirish")
def check_discount(message):
    bot.send_message(message.chat.id, "Sizga skidka berilgan ✅")

@bot.message_handler(func=lambda m: m.text == "📝 Fikr qoldirish")
def feedback(message):
    user_data[message.chat.id] = {"messages": []}
    bot.send_message(message.chat.id,
        "🤖 Yana fikringizni yozing, men tinglayapman 👇")

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
