import os, sqlite3
from fastapi import HTTPException
from pydantic import BaseModel, Field
from common import create_app

DB = os.getenv("DB_PATH", "inventory.db")
app = create_app("Inventory Service")

def conn():
    c = sqlite3.connect(DB, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000")
    c.execute("""CREATE TABLE IF NOT EXISTS inventory(
        sku TEXT PRIMARY KEY, quantity INTEGER NOT NULL CHECK(quantity >= 0))""")
    c.execute("""CREATE TABLE IF NOT EXISTS reservations(
        reservation_id TEXT PRIMARY KEY, sku TEXT NOT NULL, quantity INTEGER NOT NULL,
        status TEXT NOT NULL)""")
    return c

class StockInput(BaseModel):
    quantity: int = Field(ge=0)

class ReservationInput(BaseModel):
    reservation_id: str
    sku: str
    quantity: int = Field(gt=0)

@app.put("/api/v1/inventory/{sku}")
def set_stock(sku: str, body: StockInput):
    c=conn()
    c.execute("INSERT INTO inventory(sku,quantity) VALUES(?,?) ON CONFLICT(sku) DO UPDATE SET quantity=excluded.quantity",(sku,body.quantity))
    row=c.execute("SELECT sku,quantity FROM inventory WHERE sku=?",(sku,)).fetchone()
    c.close()
    return dict(row)

@app.get("/api/v1/inventory/{sku}")
def get_stock(sku: str):
    c=conn(); row=c.execute("SELECT sku,quantity FROM inventory WHERE sku=?",(sku,)).fetchone(); c.close()
    if not row: raise HTTPException(404, detail={"code":"SKU_NOT_FOUND","message":"SKU not found"})
    return dict(row)

@app.post("/api/v1/inventory/reservations")
def reserve(body: ReservationInput):
    c=conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        prior=c.execute("SELECT * FROM reservations WHERE reservation_id=?",(body.reservation_id,)).fetchone()
        if prior:
            if prior["sku"] != body.sku or prior["quantity"] != body.quantity:
                c.execute("ROLLBACK"); raise HTTPException(409, detail={"code":"RESERVATION_CONFLICT","message":"Reservation ID reused with different payload"})
            c.execute("COMMIT")
            return {"reservation_id":body.reservation_id,"sku":body.sku,"quantity":body.quantity,"status":prior["status"],"replayed":True}
        updated=c.execute("UPDATE inventory SET quantity=quantity-? WHERE sku=? AND quantity>=?",(body.quantity,body.sku,body.quantity))
        if updated.rowcount != 1:
            exists=c.execute("SELECT 1 FROM inventory WHERE sku=?",(body.sku,)).fetchone()
            c.execute("ROLLBACK")
            if not exists: raise HTTPException(404, detail={"code":"SKU_NOT_FOUND","message":"SKU not found"})
            raise HTTPException(409, detail={"code":"INSUFFICIENT_STOCK","message":"Not enough stock"})
        c.execute("INSERT INTO reservations VALUES(?,?,?,'RESERVED')",(body.reservation_id,body.sku,body.quantity))
        c.execute("COMMIT")
        return {"reservation_id":body.reservation_id,"sku":body.sku,"quantity":body.quantity,"status":"RESERVED","replayed":False}
    except HTTPException: raise
    except Exception:
        try: c.execute("ROLLBACK")
        except Exception: pass
        raise
    finally: c.close()

@app.post("/api/v1/inventory/reservations/{reservation_id}/release")
def release(reservation_id: str):
    c=conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT * FROM reservations WHERE reservation_id=?",(reservation_id,)).fetchone()
        if not row:
            c.execute("ROLLBACK"); raise HTTPException(404, detail={"code":"RESERVATION_NOT_FOUND","message":"Reservation not found"})
        if row["status"] == "RELEASED":
            c.execute("COMMIT"); return {"reservation_id":reservation_id,"status":"RELEASED","replayed":True}
        c.execute("UPDATE inventory SET quantity=quantity+? WHERE sku=?",(row["quantity"],row["sku"]))
        c.execute("UPDATE reservations SET status='RELEASED' WHERE reservation_id=?",(reservation_id,))
        c.execute("COMMIT")
        return {"reservation_id":reservation_id,"status":"RELEASED","replayed":False}
    finally: c.close()
