import os,asyncio,sqlite3,datetime
from aiogram import Bot,Dispatcher,types,F
from aiogram.filters import Command
from dotenv import load_dotenv
import dateparser
from aiohttp import web
load_dotenv()
BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID=int(os.getenv("YOUR_CHAT_ID"))
DIGEST_TIME=os.getenv("DIGEST_TIME","20:00")
DATA_DIR=os.getenv("DATA_DIR","/app/data")
bot=Bot(token=BOT_TOKEN)
dp=Dispatcher()
def init_db():
 os.makedirs(DATA_DIR,exist_ok=True)
 db=os.path.join(DATA_DIR,"tasks.db")
 conn=sqlite3.connect(db)
 c=conn.cursor()
 c.execute("CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,task_text TEXT,event_time DATETIME,reminded_24h BOOLEAN DEFAULT 0,reminded_1h BOOLEAN DEFAULT 0,created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
 conn.commit()
 conn.close()
 print("DB:"+db)
def parse_dt(t):
 now=datetime.datetime.now()
 p=dateparser.parse(t,settings={"PREFER_DATES_FROM":"future","RELATIVE_BASE":now})
 if p and p.hour==0 and p.minute==0:p=p.replace(hour=9,minute=0)
 if not p:p=now.replace(hour=9,minute=0)+datetime.timedelta(days=1)
 return p
@dp.message(F.voice)
async def on_voice(m):await m.answer("Voice:send text")
@dp.message()
async def on_text(m):
 t=m.text
 if t.startswith("/"):return
 try:
  et=parse_dt(t)
  db=os.path.join(DATA_DIR,"tasks.db")
  conn=sqlite3.connect(db);c=conn.cursor()
  c.execute("INSERT INTO tasks(task_text,event_time)VALUES(?,?)",(t,et.strftime("%Y-%m-%d %H:%M")))
  conn.commit();conn.close()
  r="OK:"+t+" "+et.strftime("%d.%m %H:%M")
  await m.answer(r)
 except Exception as e:await m.answer("E:"+str(e))
@dp.message(Command("start"))
async def cmd_start(m):await m.answer("Hi.Send:tomorrow 10:00 doctor")
@dp.message(Command("tasks"))
async def cmd_tasks(m):
 try:
  db=os.path.join(DATA_DIR,"tasks.db")
  conn=sqlite3.connect(db);c=conn.cursor()
  c.execute("SELECT * FROM tasks ORDER BY event_time")
  rows=c.fetchall();conn.close()
  if not rows:await m.answer("Empty");return
  r="Tasks:\n"
  for row in rows:r+="- "+row[1]+" "+row[2]+"\n"
  await m.answer(r)
 except Exception as e:await m.answer("E:"+str(e))
@dp.message(Command("tomorrow"))
async def cmd_tomorrow(m):
 try:
  tmr=(datetime.datetime.now()+datetime.timedelta(days=1)).strftime("%Y-%m-%d")
  db=os.path.join(DATA_DIR,"tasks.db")
  conn=sqlite3.connect(db);c=conn.cursor()
  c.execute("SELECT * FROM tasks WHERE event_time LIKE ?",(tmr+"%",))
  rows=c.fetchall();conn.close()
  if not rows:await m.answer("Empty tomorrow");return
  r="Tomorrow:\n"
  for row in rows:r+=row[2]+" "+row[1]+"\n"
  await m.answer(r)
 except Exception as e:await m.answer("E:"+str(e))
@dp.message(Command("clear"))
async def cmd_clear(m):
 try:
  db=os.path.join(DATA_DIR,"tasks.db")
  conn=sqlite3.connect(db);c=conn.cursor()
  c.execute("DELETE FROM tasks");conn.commit();conn.close()
  await m.answer("Cleared")
 except Exception as e:await m.answer("E:"+str(e))
async def reminders():
 while True:
  try:
   now=datetime.datetime.now()
   db=os.path.join(DATA_DIR,"tasks.db")
   conn=sqlite3.connect(db);c=conn.cursor()
   c.execute("SELECT * FROM tasks WHERE reminded_24h=0 OR reminded_1h=0")
   rows=c.fetchall()
   for row in rows:
    et=datetime.datetime.strptime(row[2],"%Y-%m-%d %H:%M")
    diff=et-now
    if datetime.timedelta(days=1)>=diff>=datetime.timedelta(days=1)-datetime.timedelta(minutes=10) and not row[3]:
     await bot.send_message(CHAT_ID,"Rem1d:"+row[1])
     c.execute("UPDATE tasks SET reminded_24h=1 WHERE id=?",(row[0],));conn.commit()
    if datetime.timedelta(hours=1)>=diff>=datetime.timedelta(hours=1)-datetime.timedelta(minutes=10) and not row[4]:
     await bot.send_message(CHAT_ID,"Rem1h:"+row[1])
     c.execute("UPDATE tasks SET reminded_1h=1 WHERE id=?",(row[0],));conn.commit()
   conn.close()
  except Exception as e:print("RE:",e)
  await asyncio.sleep(30)
async def digest():
 while True:
  try:
   now=datetime.datetime.now()
   dh,dm=map(int,DIGEST_TIME.split(":"))
   target=now.replace(hour=dh,minute=dm,second=0,microsecond=0)
   if now>=target:target+=datetime.timedelta(days=1)
   await asyncio.sleep((target-now).total_seconds())
   tmr=(datetime.datetime.now()+datetime.timedelta(days=1)).strftime("%Y-%m-%d")
   db=os.path.join(DATA_DIR,"tasks.db")
   conn=sqlite3.connect(db);c=conn.cursor()
   c.execute("SELECT * FROM tasks WHERE event_time LIKE ?",(tmr+"%",))
   rows=c.fetchall();conn.close()
   r="Digest:\n"
   for row in rows[:5]:r+=row[2]+" "+row[1]+"\n"
   if not rows:r+="Empty"
   await bot.send_message(CHAT_ID,r)
  except Exception as e:print("DE:",e)
  await asyncio.sleep(60)
async def web_srv():
 app=web.Application()
 async def ping(r):return web.Response(text="OK")
 app.router.add_get("/",ping)
 runner=web.AppRunner(app);await runner.setup()
 site=web.TCPSite(runner,"0.0.0.0",8080);await site.start()
 print("Web:8080")
async def main():
 init_db();print("Bot:start")
 await asyncio.gather(dp.start_polling(bot),reminders(),digest(),web_srv())
if __name__=="__main__":asyncio.run(main())
