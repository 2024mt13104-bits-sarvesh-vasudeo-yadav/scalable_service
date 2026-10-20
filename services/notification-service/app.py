import os, sqlite3, time
from fastapi import HTTPException
from pydantic import BaseModel
from common import create_app

DB=os.getenv("DB_PATH","notification.db")
app=create_app("Notification Service")

def conn():
 c=sqlite3.connect(DB,timeout=10,isolation_level=None); c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=10000")
 c.execute("""CREATE TABLE IF NOT EXISTS notifications(notification_id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE, order_id TEXT, message TEXT, status TEXT)""")
 return c

class NotificationInput(BaseModel):
 event_key:str
 order_id:str
 message:str

@app.post("/api/v1/notifications")
def notify(b:NotificationInput):
 delay=float(os.getenv("NOTIFICATION_DELAY_SECONDS","0"))
 if delay>0: time.sleep(min(delay,10))
 if os.getenv("NOTIFICATION_FAIL","false").lower()=="true":
  raise HTTPException(503,detail={"code":"PROVIDER_UNAVAILABLE","message":"Mock notification provider is unavailable"})
 c=conn()
 try:
  c.execute("INSERT OR IGNORE INTO notifications(event_key,order_id,message,status) VALUES(?,?,?,'SENT')",(b.event_key,b.order_id,b.message))
  row=c.execute("SELECT * FROM notifications WHERE event_key=?",(b.event_key,)).fetchone()
  return {"notification_id":row["notification_id"],"event_key":row["event_key"],"order_id":row["order_id"],"status":row["status"]}
 finally:c.close()
