import os, sqlite3, uuid
from fastapi import HTTPException
from pydantic import BaseModel, Field
from common import create_app

DB=os.getenv("DB_PATH","payment.db")
app=create_app("Payment Service")

def conn():
 c=sqlite3.connect(DB,timeout=10,isolation_level=None); c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=10000")
 c.execute("""CREATE TABLE IF NOT EXISTS payments(payment_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, order_id TEXT, amount REAL, status TEXT)""")
 return c

class PaymentInput(BaseModel):
 order_id:str
 amount:float=Field(gt=0)
 simulate_failure:bool=False
 idempotency_key:str
 
@app.post("/api/v1/payments")
def pay(b:PaymentInput):
 c=conn()
 try:
  c.execute("BEGIN IMMEDIATE")
  old=c.execute("SELECT * FROM payments WHERE idempotency_key=?",(b.idempotency_key,)).fetchone()
  if old:
   if old["order_id"]!=b.order_id or old["amount"]!=b.amount:
    c.execute("ROLLBACK"); raise HTTPException(409,detail={"code":"IDEMPOTENCY_CONFLICT","message":"Key reused with different payload"})
   c.execute("COMMIT"); return {"payment_id":old["payment_id"],"order_id":old["order_id"],"status":old["status"],"replayed":True}
  status="FAILED" if b.simulate_failure else "SUCCEEDED"
  pid=str(uuid.uuid4())
  c.execute("INSERT INTO payments VALUES(?,?,?,?,?)",(pid,b.idempotency_key,b.order_id,b.amount,status))
  c.execute("COMMIT")
  if status=="FAILED": return {"payment_id":pid,"order_id":b.order_id,"status":status,"replayed":False}
  return {"payment_id":pid,"order_id":b.order_id,"status":status,"replayed":False}
 except HTTPException: raise
 except Exception:
  try:c.execute("ROLLBACK")
  except Exception:pass
  raise
 finally:c.close()
