import os
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
