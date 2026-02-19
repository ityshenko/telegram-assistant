services:
  - type: web
    name: telegram-assistant
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python3 bot.py
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: YOUR_CHAT_ID
        sync: false
      - key: DIGEST_TIME
        value: "20:00"
      - key: DATA_DIR
        value: "/app/data"import os
import asyncio
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME = os.getenv("DIGEST_TIME", "20:00")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, 'tasks.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    sql = "CREATE TABLE IF NOT EXISTS tasks "
    sql += "(id INTEGER PRIMARY KEY, task_text TEXT, "
    sql += "event_time DATETIME, reminded_24h BOOLEAN DEFAULT 0, "
    sql += "reminded_1h BOOLEAN DEFAULT 0, "
    sql += "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    c.execute(sql)
    conn.commit()
    conn.close()
    print("DB initialized at", db_path)

def parse_datetime(text):
    now = datetime.datetime.now()
    parsed = dateparser.parse(text, 
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': 
now})
    if parsed and parsed.hour == 0 and parsed.minute == 0:
        parsed = parsed.replace(hour=9, minute=0)
    if not parsed:
        parsed = now.replace(hour=9, minute=0)
        parsed += datetime.timedelta(days=1)
    return parsed

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    msg = "Голосовые пока не работают.\n"
    msg += "Отправьте текстом: завтра в 10:00 врач"
    await message.answer(msg)

@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text.startswith('/'):
        return
    try:
        event_time = parse_datetime(text)
        db_path = os.path.join(DATA_DIR, 'tasks.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        sql = "INSERT INTO tasks (task_text, event_time) VALUES (?, 
?)"
        c.execute(sql, (text, event_time.strftime('%Y-%m-%d 
%H:%M')))
        conn.commit()
        conn.close()
        
        response = "Записал!\n\n"
        response += text + "\n"
        response += event_time.strftime('%d.%m.%Y в %H:%M') + "\n"
        response += "Напомню за 1 день и за 1 час!"
        await message.answer(response)
    except Exception as e:
        await message.answer("Ошибка: " + str(e))

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    msg = "Привет! Я ваш ассистент.\n\n"
    msg += "Отправьте задачу:\n"
    msg += "завтра в 10:00 врач\n"
    msg += "в пятницу в 14:00 встреча\n\n"
    msg += "Команды:\n"
    msg += "/tasks - все задачи\n"
    msg += "/tomorrow - на завтра\n"
    msg += "/week - на неделю\n"
    msg += "/clear - удалить всё"
    await message.answer(msg)

@dp.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    try:
        db_path = os.path.join(DATA_DIR, 'tasks.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY event_time")
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("Нет задач")
            return
        
        response = "Ваши задачи:\n\n"
        for task in tasks:
            response += "- " + task[1] + "\n"
            response += "  " + task[2] + "\n\n"
        await message.answer(response)
    except Exception as e:
        await message.answer("Ошибка: " + str(e))

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    try:
        tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1))
        date_str = tomorrow.strftime('%Y-%m-%d')
        
        db_path = os.path.join(DATA_DIR, 'tasks.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        sql = "SELECT * FROM tasks WHERE event_time LIKE ? ORDER BY 
event_time"
        c.execute(sql, (date_str + "%",))
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("На завтра задач нет")
            return
        
        response = "На завтра:\n\n"
        for task in tasks:
            time_part = task[2].split(' ')[1] if ' ' in task[2] else 
'00:00'
            response += time_part + " - " + task[1] + "\n"
        await message.answer(response)
    except Exception as e:
        await message.answer("Ошибка: " + str(e))

@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    try:
        now = datetime.datetime.now()
        week_end = now + datetime.timedelta(days=7)
        
        db_path = os.path.join(DATA_DIR, 'tasks.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        sql = "SELECT * FROM tasks WHERE event_time BETWEEN ? AND ?"
        c.execute(sql, (now.strftime('%Y-%m-%d'), 
week_end.strftime('%Y-%m-%d')))
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("На неделю задач нет")
            return
        
        response = "На неделю:\n\n"
        for task in tasks:
            response += task[2] + " - " + task[1] + "\n"
        await message.answer(response)
    except Exception as e:
        await message.answer("Ошибка: " + str(e))

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    try:
        db_path = os.path.join(DATA_DIR, 'tasks.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
        await message.answer("Все задачи удалены")
    except Exception as e:
        await message.answer("Ошибка: " + str(e))

async def check_reminders():
    print("Reminders started")
    while True:
        try:
            now = datetime.datetime.now()
            db_path = os.path.join(DATA_DIR, 'tasks.db')
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE reminded_24h = 0 OR 
reminded_1h = 0")
            tasks = c.fetchall()
            
            for task in tasks:
                event_time = datetime.datetime.strptime(task[2], 
'%Y-%m-%d %H:%M')
                diff = event_time - now
                
                day_diff = datetime.timedelta(days=1)
                hour_diff = datetime.timedelta(hours=1)
                ten_min = datetime.timedelta(minutes=10)
                
                if day_diff >= diff >= day_diff - ten_min:
                    if not task[3]:
                        msg = "Напоминание (1 день)\n\n"
                        msg += task[1] + "\n"
                        msg += "Завтра в " + 
event_time.strftime('%H:%M')
                        await bot.send_message(CHAT_ID, msg)
                        c.execute("UPDATE tasks SET reminded_24h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
                
                if hour_diff >= diff >= hour_diff - ten_min:
                    if not task[4]:
                        msg = "Напоминание (1 час)\n\n"
                        msg += task[1] + "\n"
                        msg += "Сегодня в " + 
event_time.strftime('%H:%M')
                        await bot.send_message(CHAT_ID, msg)
                        c.execute("UPDATE tasks SET reminded_1h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
            
            conn.close()
        except Exception as e:
            print("Reminder error:", e)
        await asyncio.sleep(30)

async def evening_digest():
    print("Digest started for", DIGEST_TIME)
    while True:
        try:
            now = datetime.datetime.now()
            parts = DIGEST_TIME.split(':')
            digest_hour = int(parts[0])
            digest_minute = int(parts[1])
            
            target = now.replace(hour=digest_hour, 
minute=digest_minute, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            
            wait_secs = (target - now).total_seconds()
            print("Waiting", wait_secs/3600, "hours for digest")
            await asyncio.sleep(wait_secs)
            
            tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            week_end = (datetime.datetime.now() + 
datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            
            db_path = os.path.join(DATA_DIR, 'tasks.db')
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            sql = "SELECT * FROM tasks WHERE event_time LIKE ? ORDER 
BY event_time"
            c.execute(sql, (tomorrow + "%",))
            tomorrow_tasks = c.fetchall()
            
            sql = "SELECT * FROM tasks WHERE event_time BETWEEN ? 
AND ? ORDER BY event_time"
            c.execute(sql, (now.strftime('%Y-%m-%d'), week_end))
            week_tasks = c.fetchall()
            conn.close()
            
            response = "Вечерний дайджест (" + 
now.strftime('%d.%m.%Y') + ")\n\n"
            
            if tomorrow_tasks:
                response += "На завтра:\n"
                for task in tomorrow_tasks:
                    time_part = task[2].split(' ')[1] if ' ' in 
task[2] else '00:00'
                    response += time_part + " - " + task[1] + "\n"
            else:
                response += "На завтра: задач нет\n"
            
            if week_tasks:
                response += "\nНа неделю:\n"
                for task in week_tasks[:5]:
                    response += task[2] + " - " + task[1] + "\n"
            
            await bot.send_message(CHAT_ID, response)
            print("Digest sent")
        except Exception as e:
            print("Digest error:", e)
        await asyncio.sleep(60)

async def start_web_server():
    app = web.Application()
    
    async def handle_ping(request):
        return web.Response(text="OK")
    
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Web server on port 8080")

async def main():
    init_db()
    print("Bot starting...")
    await asyncio.gather(
        dp.start_polling(bot),
        check_reminders(),
        evening_digest(),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())import 
os
import asyncio
import sqlite3
import datetime
import wave
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web
from vosk import Model, KaldiRecognizer

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME = os.getenv("DIGEST_TIME", "20:00")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
model = None

def load_vosk_model():
    global model
    try:
        model_path = os.path.join(DATA_DIR, "ru")
        if os.path.exists(model_path):
            model = Model(model_path)
            print(f"✅ Vosk loaded from {model_path}")
        else:
            print(f"❌ Vosk model not found at {model_path}")
    except Exception as e:
        print(f"❌ Vosk error: {e}")

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY, 
                  task_text TEXT, 
                  event_time DATETIME, 
                  reminded_24h BOOLEAN DEFAULT 0, 
                  reminded_1h BOOLEAN DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("✅ DB initialized")

def recognize_voice(file_path):
    if model is None:
        return None
    try:
        wf = wave.open(file_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text += result.get("text", "") + " "
        final = json.loads(rec.FinalResult())
        text += final.get("text", "")
        wf.close()
        return text.strip()
    except Exception as e:
        print(f"❌ Voice error: {e}")
        return None

def parse_datetime(text):
    now = datetime.datetime.now()
    parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 
'future', 'RELATIVE_BASE': now})
    if parsed and parsed.hour == 0 and parsed.minute == 0:
        parsed = parsed.replace(hour=9, minute=0)
    return parsed or (now.replace(hour=9, minute=0) + 
datetime.timedelta(days=1))

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    await message.answer("🎧 Распознаю...")
    try:
        file = await bot.download_file((await 
bot.get_file(message.voice.file_id)).file_path)
        text = recognize_voice(file.name)
        if not text:
            await message.answer("⚠️ Не распознал. Отправьте 
текстом: 'завтра в 10:00 врач'")
            return
        event_time = parse_datetime(text)
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES 
(?, ?)", (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Записал!\n\n📝 {text}\n📅 
{event_time.strftime('%d.%m.%Y в %H:%M')}\n🔔 Напомню за 1 день и за 
1 час!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text.startswith('/'):
        return
    try:
        event_time = parse_datetime(text)
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES 
(?, ?)", (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Записал!\n\n📝 {text}\n📅 
{event_time.strftime('%d.%m.%Y в %H:%M')}\n🔔 Напомню за 1 день и за 
1 час!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Отправьте задачу:\n• 'завтра в 
10:00 врач'\n• 'в пятницу в 14:00 встреча'\n\n📋 /tasks — все 
задачи\n📅 /tomorrow — на завтра\n📆 /week — на неделю\n🗑 /clear — 
удалить всё")

@dp.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY event_time")
        tasks = c.fetchall()
        conn.close()
        if not tasks:
            await message.answer("📭 Нет задач")
            return
        text = "📋 **Ваши задачи:**\n\n"
        for task in tasks:
            text += f"⏳ {task[1]}\n   📅 {task[2]}\n\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    try:
        tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE event_time LIKE ? ORDER 
BY event_time", (f"{tomorrow}%",))
        tasks = c.fetchall()
        conn.close()
        if not tasks:
            await message.answer("📭 На завтра пусто")
            return
        text = "📅 **На завтра:**\n\n"
        for task in tasks:
            time = task[2].split(' ')[1] if ' ' in task[2] else 
'00:00'
            text += f"⏰ {time} — {task[1]}\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    try:
        now = datetime.datetime.now()
        week_end = now + datetime.timedelta(days=7)
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE event_time BETWEEN ? 
AND ? ORDER BY event_time", (now.strftime('%Y-%m-%d'), 
week_end.strftime('%Y-%m-%d')))
        tasks = c.fetchall()
        conn.close()
        if not tasks:
            await message.answer("📭 На неделю задач нет")
            return
        text = "📆 **На неделю:**\n\n"
        for task in tasks:
            text += f"▫️ {task[2]} — {task[1]}\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'tasks.db'))
        c = conn.cursor()
        c.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
        await message.answer("🗑 Всё удалено")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def check_reminders():
    while True:
        try:
            now = datetime.datetime.now()
            conn = sqlite3.connect(os.path.join(DATA_DIR, 
'tasks.db'))
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE reminded_24h = 0 OR 
reminded_1h = 0")
            tasks = c.fetchall()
            for task in tasks:
                event_time = datetime.datetime.strptime(task[2], 
'%Y-%m-%d %H:%M')
                diff = event_time - now
                if datetime.timedelta(days=1) >= diff >= 
datetime.timedelta(days=1) - datetime.timedelta(minutes=10):
                    if not task[3]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
день**\n\n📝 {task[1]}\n📅 Завтра в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_24h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
                if datetime.timedelta(hours=1) >= diff >= 
datetime.timedelta(hours=1) - datetime.timedelta(minutes=10):
                    if not task[4]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
час**\n\n📝 {task[1]}\n📅 Сегодня в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_1h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ Reminder error: {e}")
        await asyncio.sleep(30)

async def evening_digest():
    while True:
        try:
            now = datetime.datetime.now()
            digest_hour, digest_minute = map(int, 
DIGEST_TIME.split(':'))
            target_time = now.replace(hour=digest_hour, 
minute=digest_minute, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            await asyncio.sleep((target_time - now).total_seconds())
            tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            week_end = (datetime.datetime.now() + 
datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            conn = sqlite3.connect(os.path.join(DATA_DIR, 
'tasks.db'))
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE event_time LIKE ? 
ORDER BY event_time", (f"{tomorrow}%",))
            tomorrow_tasks = c.fetchall()
            c.execute("SELECT * FROM tasks WHERE event_time BETWEEN 
? AND ? ORDER BY event_time", (now.strftime('%Y-%m-%d'), week_end))
            week_tasks = c.fetchall()
            conn.close()
            text = f"📊 **Вечерний дайджест** 
({now.strftime('%d.%m.%Y')})\n\n"
            if tomorrow_tasks:
                text += "📅 **На завтра:**\n"
                for task in tomorrow_tasks:
                    time = task[2].split(' ')[1] if ' ' in task[2] 
else '00:00'
                    text += f"⏰ {time} — {task[1]}\n"
            else:
                text += "📅 **На завтра:** задач нет\n"
            if week_tasks:
                text += "\n📆 **На неделю:**\n"
                for task in week_tasks[:5]:
                    text += f"▫️ {task[2]} — {task[1]}\n"
            await bot.send_message(CHAT_ID, text)
        except Exception as e:
            print(f"❌ Digest error: {e}")
        await asyncio.sleep(60)

async def start_web_server():
    app = web.Application()
    async def handle_ping(request):
        return web.Response(text="OK")
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web server on port 8080")

async def main():
    load_vosk_model()
    init_db()
    print("🤖 Bot starting...")
    await asyncio.gather(dp.start_polling(bot), check_reminders(), 
evening_digest(), start_web_server())

if __name__ == "__main__":
    asyncio.run(main())import 
os import 
asyncio 
import sqlite3
import datetime
import wave
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web
from vosk import Model, KaldiRecognizer

# Загружаем настройки
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME = os.getenv("DIGEST_TIME", "20:00")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация Vosk модели
MODEL_PATH = "models/ru"
model = None

def load_vosk_model():
    global model
    try:
        if os.path.exists(MODEL_PATH):
            model = Model(MODEL_PATH)
            print(f"✅ Vosk модель загружена из {MODEL_PATH}")
        else:
            print(f"❌ Модель Vosk не найдена в {MODEL_PATH}")
    except Exception as e:
        print(f"❌ Ошибка загрузки Vosk: {e}")

# База данных
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY, 
                  task_text TEXT, 
                  event_time DATETIME, 
                  reminded_24h BOOLEAN DEFAULT 0, 
                  reminded_1h BOOLEAN DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# Распознавание голоса через Vosk
def recognize_voice_vosk(file_path):
    if model is None:
        print("❌ Vosk модель не загружена")
        return None
    
    try:
        wf = wave.open(file_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text += result.get("text", "") + " "
        
        final_result = json.loads(rec.FinalResult())
        text += final_result.get("text", "")
        
        wf.close()
        return text.strip()
    except Exception as e:
        print(f"❌ Ошибка распознавания: {e}")
        return None

# Парсинг даты из текста
def parse_datetime_from_text(text):
    now = datetime.datetime.now()
    parsed = dateparser.parse(
        text,
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': 
now}
    )
    if parsed:
        if parsed.hour == 0 and parsed.minute == 0:
            parsed = parsed.replace(hour=9, minute=0)
        return parsed
    return now.replace(hour=9, minute=0) + 
datetime.timedelta(days=1)

# Обработка голосовых
@dp.message(F.voice)
async def handle_voice(message: types.Message):
    await message.answer("🎧 Распознаю голосовое...")
    
    try:
        # Скачиваем файл
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file.file_path)
        
        print(f"🎤 Получено голосовое: {downloaded_file.name}")
        
        # Распознаём через Vosk
        text = recognize_voice_vosk(downloaded_file.name)
        
        print(f"📝 Распознано: {text}")
        
        if not text:
            await message.answer(
                "⚠️ Не удалось распознать голосовое.\n\n"
                "💡 Отправьте задачу текстом:\n"
                "• 'завтра в 10:00 врач'\n"
                "• 'в пятницу в 14:00 встреча'"
            )
            return
        
        event_time = parse_datetime_from_text(text)
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES 
(?, ?)",
                  (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Записал!\n\n"
            f"📝 {text}\n"
            f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"🔔 Напомню за 1 день и за 1 час!"
        )
    except Exception as e:
        print(f"❌ Ошибка обработки голосового: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

# Обработка текста
@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text.startswith('/'):
        return
    
    try:
        event_time = parse_datetime_from_text(text)
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES 
(?, ?)",
                  (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Записал!\n\n"
            f"📝 {text}\n"
            f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"🔔 Напомню за 1 день и за 1 час!"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я ваш ассистент.\n\n"
        "🎤 Отправьте голосовое ИЛИ текст:\n"
        "• 'завтра в 10:00 врач'\n"
        "• 'в пятницу в 14:00 встреча'\n\n"
        "📋 /tasks — все задачи\n"
        "📅 /tomorrow — на завтра\n"
        "📆 /week — на неделю\n"
        "🗑 /clear — удалить всё"
    )

# Команда /tasks
@dp.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    try:
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY event_time")
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("📭 Нет задач")
            return
        
        text = "📋 **Ваши задачи:**\n\n"
        for task in tasks:
            text += f"⏳ {task[1]}\n   📅 {task[2]}\n\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Команда /tomorrow
@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    try:
        tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE event_time LIKE ? ORDER 
BY event_time", (f"{tomorrow}%",))
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("📭 На завтра пусто")
            return
        
        text = "📅 **На завтра:**\n\n"
        for task in tasks:
            time = task[2].split(' ')[1] if ' ' in task[2] else 
'00:00'
            text += f"⏰ {time} — {task[1]}\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Команда /week
@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    try:
        now = datetime.datetime.now()
        week_end = now + datetime.timedelta(days=7)
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE event_time BETWEEN ? 
AND ? ORDER BY event_time",
                  (now.strftime('%Y-%m-%d'), 
week_end.strftime('%Y-%m-%d')))
        tasks = c.fetchall()
        conn.close()
        
        if not tasks:
            await message.answer("📭 На неделю задач нет")
            return
        
        text = "📆 **На неделю:**\n\n"
        for task in tasks:
            text += f"▫️ {task[2]} — {task[1]}\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Команда /clear
@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    try:
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
        await message.answer("🗑 Всё удалено")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Напоминания
async def check_reminders():
    print("⏰ Планировщик напоминаний запущен")
    while True:
        try:
            now = datetime.datetime.now()
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE reminded_24h = 0 OR 
reminded_1h = 0")
            tasks = c.fetchall()
            
            for task in tasks:
                event_time = datetime.datetime.strptime(task[2], 
'%Y-%m-%d %H:%M')
                diff = event_time - now
                
                if datetime.timedelta(days=1) >= diff >= 
datetime.timedelta(days=1) - datetime.timedelta(minutes=10):
                    if not task[3]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
день**\n\n📝 {task[1]}\n📅 Завтра в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_24h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
                        print(f"✅ Напоминание за 24ч: {task[1]}")
                
                if datetime.timedelta(hours=1) >= diff >= 
datetime.timedelta(hours=1) - datetime.timedelta(minutes=10):
                    if not task[4]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
час**\n\n📝 {task[1]}\n📅 Сегодня в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_1h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
                        print(f"✅ Напоминание за 1ч: {task[1]}")
            
            conn.close()
        except Exception as e:
            print(f"❌ Ошибка планировщика: {e}")
        
        await asyncio.sleep(30)

# Вечерний дайджест
async def evening_digest():
    print(f"📊 Вечерний дайджест настроен на {DIGEST_TIME}")
    while True:
        try:
            now = datetime.datetime.now()
            digest_hour, digest_minute = map(int, 
DIGEST_TIME.split(':'))
            
            target_time = now.replace(hour=digest_hour, 
minute=digest_minute, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            
            wait_seconds = (target_time - now).total_seconds()
            print(f"⏳ До дайджеста {wait_seconds/3600:.1f} часов")
            await asyncio.sleep(wait_seconds)
            
            tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            week_end = (datetime.datetime.now() + 
datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            
            c.execute("SELECT * FROM tasks WHERE event_time LIKE ? 
ORDER BY event_time", (f"{tomorrow}%",))
            tomorrow_tasks = c.fetchall()
            
            c.execute("SELECT * FROM tasks WHERE event_time BETWEEN 
? AND ? ORDER BY event_time",
                      (now.strftime('%Y-%m-%d'), week_end))
            week_tasks = c.fetchall()
            
            conn.close()
            
            text = f"📊 **Вечерний дайджест** 
({now.strftime('%d.%m.%Y')})\n\n"
            
            if tomorrow_tasks:
                text += "📅 **На завтра:**\n"
                for task in tomorrow_tasks:
                    time = task[2].split(' ')[1] if ' ' in task[2] 
else '00:00'
                    text += f"⏰ {time} — {task[1]}\n"
            else:
                text += "📅 **На завтра:** задач нет\n"
            
            if week_tasks:
                text += "\n📆 **На неделю:**\n"
                for task in week_tasks[:5]:
                    text += f"▫️ {task[2]} — {task[1]}\n"
            
            await bot.send_message(CHAT_ID, text)
            print("✅ Дайджест отправлен")
        except Exception as e:
            print(f"❌ Ошибка дайджеста: {e}")
        
        await asyncio.sleep(60)

# Web-сервер для ping
async def start_web_server():
    app = web.Application()
    
    async def handle_ping(request):
        return web.Response(text="OK - Bot is alive")
    
    app.router.add_get('/', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web-сервер запущен на порту 8080")

# Запуск
async def main():
    load_vosk_model()
    init_db()
    print("🤖 Бот запущен...")
    await asyncio.gather(
        dp.start_polling(bot),
        check_reminders(),
        evening_digest(),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())import 
os
import asyncio
import sqlite3
import datetime
import wave
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web
from vosk import Model, KaldiRecognizer

# Загружаем настройки
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME = os.getenv("DIGEST_TIME", "20:00")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация Vosk модели
MODEL_PATH = "models/ru"
model = None

def load_vosk_model():
    global model
    try:
        if os.path.exists(MODEL_PATH):
            model = Model(MODEL_PATH)
            print(f"✅ Vosk модель загружена из {MODEL_PATH}")
        else:
            print(f"⚠️ Модель Vosk не найдена в {MODEL_PATH}")
    except Exception as e:
        print(f"❌ Ошибка загрузки Vosk: {e}")

# База данных
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY, 
                  task_text TEXT, 
                  event_time DATETIME, 
                  reminded_24h BOOLEAN DEFAULT 0, 
                  reminded_1h BOOLEAN DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Распознавание голоса через Vosk
def recognize_voice_vosk(file_path):
    if model is None:
        return None
    
    try:
        wf = wave.open(file_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        
        text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text += result.get("text", "") + " "
        
        final_result = json.loads(rec.FinalResult())
        text += final_result.get("text", "")
        
        wf.close()
        return text.strip()
    except Exception as e:
        print(f"Ошибка распознавания: {e}")
        return None

# Парсинг даты из текста
def parse_datetime_from_text(text):
    now = datetime.datetime.now()
    parsed = dateparser.parse(
        text,
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': 
now}
    )
    if parsed:
        if parsed.hour == 0 and parsed.minute == 0:
            parsed = parsed.replace(hour=9, minute=0)
        return parsed
    return now.replace(hour=9, minute=0) + 
datetime.timedelta(days=1)

# Обработка голосовых
@dp.message(F.voice)
async def handle_voice(message: types.Message):
    await message.answer("🎧 Обрабатываю голосовое...")
    
    try:
        # Скачиваем файл
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file.file_path)
        
        # Пробуем распознать через Vosk
        text = recognize_voice_vosk(downloaded_file.name)
        
        if not text:
            await message.answer(
                "⚠️ Не удалось распознать голосовое.\n\n"
                "💡 Отправьте задачу текстом, например:\n"
                "• 'завтра в 10:00 врач'\n"
                "• 'в пятницу в 14:00 встреча'"
            )
            return
        
        event_time = parse_datetime_from_text(text)
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES 
(?, ?)",
                  (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Записал!\n\n"
            f"📝 {text}\n"
            f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"🔔 Напомню за 1 день и за 1 час!"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Обработка текста
@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text.startswith('/'):
        return
    
    event_time = parse_datetime_from_text(text)
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (task_text, event_time) VALUES (?, 
?)",
              (text, event_time.strftime('%Y-%m-%d %H:%M')))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ Записал!\n\n"
        f"📝 {text}\n"
        f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
        f"🔔 Напомню за 1 день и за 1 час!"
    )

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я ваш ассистент.\n\n"
        " Отправьте текст с задачей:\n"
        "• 'завтра в 10:00 врач'\n"
        "• 'в пятницу в 14:00 встреча'\n\n"
        "🎤 Или отправьте голосовое (распознаю)\n\n"
        "📋 /tasks — все задачи\n"
        "📅 /tomorrow — на завтра\n"
        "📆 /week — на неделю\n"
        "🗑 /clear — удалить всё"
    )

# Команда /tasks
@dp.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks ORDER BY event_time")
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 Нет задач")
        return
    
    text = "📋 **Ваши задачи:**\n\n"
    for task in tasks:
        text += f"⏳ {task[1]}\n   📅 {task[2]}\n\n"
    await message.answer(text)

# Команда /tomorrow
@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE event_time LIKE ? ORDER BY 
event_time", (f"{tomorrow}%",))
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 На завтра пусто")
        return
    
    text = "📅 **На завтра:**\n\n"
    for task in tasks:
        time = task[2].split(' ')[1] if ' ' in task[2] else '00:00'
        text += f"⏰ {time} — {task[1]}\n"
    await message.answer(text)

# Команда /week
@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    now = datetime.datetime.now()
    week_end = now + datetime.timedelta(days=7)
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE event_time BETWEEN ? AND ? 
ORDER BY event_time",
              (now.strftime('%Y-%m-%d'), 
week_end.strftime('%Y-%m-%d')))
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 На неделю задач нет")
        return
    
    text = "📆 **На неделю:**\n\n"
    for task in tasks:
        text += f"▫️ {task[2]} — {task[1]}\n"
    await message.answer(text)

# Команда /clear
@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()
    await message.answer("🗑 Всё удалено")

# Напоминания
async def check_reminders():
    while True:
        try:
            now = datetime.datetime.now()
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE reminded_24h = 0 OR 
reminded_1h = 0")
            tasks = c.fetchall()
            
            for task in tasks:
                event_time = datetime.datetime.strptime(task[2], 
'%Y-%m-%d %H:%M')
                diff = event_time - now
                
                if datetime.timedelta(days=1) >= diff >= 
datetime.timedelta(days=1) - datetime.timedelta(minutes=10):
                    if not task[3]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
день**\n\n📝 {task[1]}\n📅 Завтра в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_24h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
                
                if datetime.timedelta(hours=1) >= diff >= 
datetime.timedelta(hours=1) - datetime.timedelta(minutes=10):
                    if not task[4]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 
час**\n\n📝 {task[1]}\n📅 Сегодня в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_1h = 1 
WHERE id = ?", (task[0],))
                        conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"Ошибка: {e}")
        
        await asyncio.sleep(30)

# Вечерний дайджест
async def evening_digest():
    while True:
        try:
            now = datetime.datetime.now()
            digest_hour, digest_minute = map(int, 
DIGEST_TIME.split(':'))
            
            target_time = now.replace(hour=digest_hour, 
minute=digest_minute, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            
            wait_seconds = (target_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            tomorrow = (datetime.datetime.now() + 
datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            week_end = (datetime.datetime.now() + 
datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            
            c.execute("SELECT * FROM tasks WHERE event_time LIKE ? 
ORDER BY event_time", (f"{tomorrow}%",))
            tomorrow_tasks = c.fetchall()
            
            c.execute("SELECT * FROM tasks WHERE event_time BETWEEN 
? AND ? ORDER BY event_time",
                      (now.strftime('%Y-%m-%d'), week_end))
            week_tasks = c.fetchall()
            
            conn.close()
            
            text = f"📊 **Вечерний дайджест** 
({now.strftime('%d.%m.%Y')})\n\n"
            
            if tomorrow_tasks:
                text += "📅 **На завтра:**\n"
                for task in tomorrow_tasks:
                    time = task[2].split(' ')[1] if ' ' in task[2] 
else '00:00'
                    text += f"⏰ {time} — {task[1]}\n"
            else:
                text += "📅 **На завтра:** задач нет\n"
            
            if week_tasks:
                text += "\n📆 **На неделю:**\n"
                for task in week_tasks[:5]:
                    text += f"▫️ {task[2]} — {task[1]}\n"
            
            await bot.send_message(CHAT_ID, text)
        except Exception as e:
            print(f"Ошибка дайджеста: {e}")
        
        await asyncio.sleep(60)

# Web-сервер для ping
async def start_web_server():
    app = web.Application()
    
    async def handle_ping(request):
        return web.Response(text="OK")
    
    app.router.add_get('/', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web-сервер запущен на порту 8080")

# Запуск
async def main():
    load_vosk_model()
    init_db()
    print("🤖 Бот запущен...")
    await asyncio.gather(
        dp.start_polling(bot),
        check_reminders(),
        evening_digest(),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())import 
os
import asyncio
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web

# Загружаем настройки
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME = os.getenv("DIGEST_TIME", "20:00")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# База данных
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY, 
                  task_text TEXT, 
                  event_time DATETIME, 
                  reminded_24h BOOLEAN DEFAULT 0, 
                  reminded_1h BOOLEAN DEFAULT 0,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Парсинг даты из текста
def parse_datetime_from_text(text):
    now = datetime.datetime.now()
    parsed = dateparser.parse(
        text,
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': now}
    )
    if parsed:
        if parsed.hour == 0 and parsed.minute == 0:
            parsed = parsed.replace(hour=9, minute=0)
        return parsed
    return now.replace(hour=9, minute=0) + datetime.timedelta(days=1)

# Обработка голосовых
@dp.message(F.voice)
async def handle_voice(message: types.Message):
    await message.answer("🎧 Обрабатываю...")
    
    try:
        if message.voice.transcription:
            text = message.voice.transcription
        else:
            await message.answer(
                "⚠️ Включите транскрибацию в Telegram:\n"
                "Настройки → Приватность → Голосовые сообщения → Преобразовывать в текст"
            )
            return
        
        if not text:
            await message.answer("❌ Не удалось распознать речь.")
            return
        
        event_time = parse_datetime_from_text(text)
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task_text, event_time) VALUES (?, ?)",
                  (text, event_time.strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Записал!\n\n"
            f"📝 {text}\n"
            f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"🔔 Напомню за 1 день и за 1 час!"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Обработка текста
@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text.startswith('/'):
        return
    
    event_time = parse_datetime_from_text(text)
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (task_text, event_time) VALUES (?, ?)",
              (text, event_time.strftime('%Y-%m-%d %H:%M')))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ Записал!\n\n"
        f"📝 {text}\n"
        f"📅 {event_time.strftime('%d.%m.%Y в %H:%M')}\n"
        f"🔔 Напомню за 1 день и за 1 час!"
    )

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я ваш ассистент.\n\n"
        "🎤 Отправьте голосовое или текст\n"
        "📋 /tasks — все задачи\n"
        "📅 /tomorrow — на завтра\n"
        "📆 /week — на неделю\n"
        "🗑 /clear — удалить всё"
    )

# Команда /tasks
@dp.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks ORDER BY event_time")
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 Нет задач")
        return
    
    text = "📋 **Ваши задачи:**\n\n"
    for task in tasks:
        text += f"⏳ {task[1]}\n   📅 {task[2]}\n\n"
    await message.answer(text)

# Команда /tomorrow
@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE event_time LIKE ? ORDER BY event_time", (f"{tomorrow}%",))
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 На завтра пусто")
        return
    
    text = "📅 **На завтра:**\n\n"
    for task in tasks:
        time = task[2].split(' ')[1] if ' ' in task[2] else '00:00'
        text += f"⏰ {time} — {task[1]}\n"
    await message.answer(text)

# Команда /week
@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    now = datetime.datetime.now()
    week_end = now + datetime.timedelta(days=7)
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE event_time BETWEEN ? AND ? ORDER BY event_time",
              (now.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await message.answer("📭 На неделю задач нет")
        return
    
    text = "📆 **На неделю:**\n\n"
    for task in tasks:
        text += f"▫️ {task[2]} — {task[1]}\n"
    await message.answer(text)

# Команда /clear
@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()
    await message.answer("🗑 Всё удалено")

# Напоминания
async def check_reminders():
    while True:
        try:
            now = datetime.datetime.now()
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            c.execute("SELECT * FROM tasks WHERE reminded_24h = 0 OR reminded_1h = 0")
            tasks = c.fetchall()
            
            for task in tasks:
                event_time = datetime.datetime.strptime(task[2], '%Y-%m-%d %H:%M')
                diff = event_time - now
                
                if datetime.timedelta(days=1) >= diff >= datetime.timedelta(days=1) - datetime.timedelta(minutes=10):
                    if not task[3]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 день**\n\n📝 {task[1]}\n📅 Завтра в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_24h = 1 WHERE id = ?", (task[0],))
                        conn.commit()
                
                if datetime.timedelta(hours=1) >= diff >= datetime.timedelta(hours=1) - datetime.timedelta(minutes=10):
                    if not task[4]:
                        await bot.send_message(CHAT_ID, f"⏰ **1 час**\n\n📝 {task[1]}\n📅 Сегодня в {event_time.strftime('%H:%M')}")
                        c.execute("UPDATE tasks SET reminded_1h = 1 WHERE id = ?", (task[0],))
                        conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"Ошибка: {e}")
        
        await asyncio.sleep(30)

# Вечерний дайджест
async def evening_digest():
    while True:
        try:
            now = datetime.datetime.now()
            digest_hour, digest_minute = map(int, DIGEST_TIME.split(':'))
            
            target_time = now.replace(hour=digest_hour, minute=digest_minute, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            
            wait_seconds = (target_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            week_end = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            
            c.execute("SELECT * FROM tasks WHERE event_time LIKE ? ORDER BY event_time", (f"{tomorrow}%",))
            tomorrow_tasks = c.fetchall()
            
            c.execute("SELECT * FROM tasks WHERE event_time BETWEEN ? AND ? ORDER BY event_time",
                      (now.strftime('%Y-%m-%d'), week_end))
            week_tasks = c.fetchall()
            
            conn.close()
            
            text = f"📊 **Вечерний дайджест** ({now.strftime('%d.%m.%Y')})\n\n"
            
            if tomorrow_tasks:
                text += "📅 **На завтра:**\n"
                for task in tomorrow_tasks:
                    time = task[2].split(' ')[1] if ' ' in task[2] else '00:00'
                    text += f"⏰ {time} — {task[1]}\n"
            else:
                text += "📅 **На завтра:** задач нет\n"
            
            if week_tasks:
                text += "\n📆 **На неделю:**\n"
                for task in week_tasks[:5]:
                    text += f"▫️ {task[2]} — {task[1]}\n"
            
            await bot.send_message(CHAT_ID, text)
        except Exception as e:
            print(f"Ошибка дайджеста: {e}")
        
        await asyncio.sleep(60)

# Web-сервер для ping
async def start_web_server():
    app = web.Application()
    
    async def handle_ping(request):
        return web.Response(text="OK")
    
    app.router.add_get('/', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web-сервер запущен на порту 8080")

# Запуск
async def main():
    init_db()
    print("🤖 Бот запущен...")
    await asyncio.gather(
        dp.start_polling(bot),
        check_reminders(),
        evening_digest(),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
