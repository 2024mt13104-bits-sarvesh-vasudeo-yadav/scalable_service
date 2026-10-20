import os, sqlite3, uuid, json, hashlib, time, random, logging
import httpx
from fastapi import HTTPException, Request, Header
from pydantic import BaseModel, Field
from common import create_app
DB=os.getenv("DB_PATH","orders.db")
INVENTORY_URL=os.getenv("INVENTORY_URL","http://127.0.0.1:8002")
PAYMENT_URL=os.getenv("PAYMENT_URL","http://127.0.0.1:8003")
NOTIFICATION_URL=os.getenv("NOTIFICATION_URL","http://127.0.0.1:8004")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format='{"level":"%(levelname)s","message":"%(message)s"}')
log=logging.getLogger("order-service")
app=create_app("Order Service")
def conn():
 c=sqlite3.connect(DB,timeout=10,isolation_level=None); c.row_factory=sqlite3.Row
 c.execute("PRAGMA busy_timeout=10000")
 c.execute("""CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY, sku TEXT, quantity INTEGER, amount REAL, status TEXT, reservation_id TEXT, payment_id TEXT, error TEXT)""")
 c.execute("""CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response_json TEXT NOT NULL, status_code INTEGER NOT NULL)""")
 return c

class OrderInput(BaseModel):
 sku:str=Field(min_length=1)
 quantity:int=Field(gt=0,le=10000)
 amount:float=Field(gt=0)
 simulate_failure:bool=False

def downstream(method,url,*,headers=None,json_body=None,retries=2):
 last=None
 for attempt in range(retries+1):
  try:
   with httpx.Client(timeout=1.5) as client:
    r=client.request(method,url,headers=headers,json=json_body)
   if r.status_code>=500 and attempt<retries: raise httpx.HTTPStatusError("retryable",request=r.request,response=r)
   return r
  except (httpx.TimeoutException,httpx.ConnectError,httpx.HTTPStatusError) as e:
   last=e
   if attempt<retries: time.sleep((0.1*(2**attempt))+random.uniform(0,0.08))
 raise last

@app.post("/api/v1/orders")
def create_order(
    b: OrderInput,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key")
):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    fingerprint = hashlib.sha256(b.model_dump_json().encode()).hexdigest()
    c = conn()

    try:
        c.execute("BEGIN IMMEDIATE")
        old = c.execute(
            "SELECT * FROM idempotency WHERE key=?",
            (idempotency_key,)
        ).fetchone()

        if old:
            if old["fingerprint"] != fingerprint:
                c.execute("ROLLBACK")
                raise HTTPException(
                    409,
                    detail={
                        "code": "IDEMPOTENCY_CONFLICT",
                        "message": "Idempotency-Key reused with a different request body"
                    }
                )

            response = json.loads(old["response_json"])
            c.execute("COMMIT")
            log.info(
                "idempotency replay key=%s request_id=%s",
                idempotency_key, rid
            )
            response["replayed"] = True
            return response

        oid = str(uuid.uuid4())
        reservation = oid

        c.execute(
            "INSERT INTO orders VALUES(?,?,?,?,'PENDING',?,NULL,NULL)",
            (oid, b.sku, b.quantity, b.amount, reservation)
        )

        # Save the idempotency key before making downstream calls.
        c.execute(
            "INSERT INTO idempotency VALUES(?,?,?,?)",
            (
                idempotency_key,
                fingerprint,
                json.dumps({"order_id": oid, "status": "PENDING"}),
                202
            )
        )
        c.execute("COMMIT")

    except HTTPException:
        raise
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        c.close()

    # Call Inventory and Payment services.
    headers = {"X-Request-ID": rid}

    try:
        inv = downstream(
            "POST",
            f"{INVENTORY_URL}/api/v1/inventory/reservations",
            headers=headers,
            json_body={
                "reservation_id": reservation,
                "sku": b.sku,
                "quantity": b.quantity
            }
        )

        if inv.status_code >= 400:
            raise HTTPException(
                inv.status_code,
                detail={
                    "code": "INVENTORY_REJECTED",
                    "message": "Inventory reservation failed",
                    "downstream": inv.json()
                }
            )

        pay = downstream(
            "POST",
            f"{PAYMENT_URL}/api/v1/payments",
            headers=headers,
            json_body={
                "order_id": oid,
                "amount": b.amount,
                "simulate_failure": b.simulate_failure,
                "idempotency_key": oid
            }
        )

        if pay.status_code >= 400:
            raise HTTPException(
                502,
                detail={
                    "code": "PAYMENT_SERVICE_ERROR",
                    "message": "Payment service returned an error"
                }
            )

        pdata = pay.json()

        if pdata["status"] != "SUCCEEDED":
            downstream(
                "POST",
                f"{INVENTORY_URL}/api/v1/inventory/reservations/{reservation}/release",
                headers=headers
            )
            status = "FAILED"
            err = "MOCK_PAYMENT_FAILED"
            payment_id = pdata.get("payment_id")
        else:
            status = "CONFIRMED"
            err = None
            payment_id = pdata.get("payment_id")

    except HTTPException as e:
        status = "FAILED"
        err = str(e.detail)
        payment_id = None

        # Release inventory if a reservation was created.
        try:
            downstream(
                "POST",
                f"{INVENTORY_URL}/api/v1/inventory/reservations/{reservation}/release",
                headers=headers
            )
        except Exception:
            pass

    except Exception as e:
        status = "FAILED"
        err = "DOWNSTREAM_UNAVAILABLE"
        payment_id = None

        # Best-effort compensation.
        try:
            downstream(
                "POST",
                f"{INVENTORY_URL}/api/v1/inventory/reservations/{reservation}/release",
                headers=headers
            )
        except Exception:
            pass

    # Save the final order result.
    c = conn()
    try:
        c.execute(
            "UPDATE orders SET status=?,payment_id=?,error=? WHERE order_id=?",
            (status, payment_id, err, oid)
        )

        response = {
            "order_id": oid,
            "status": status,
            "payment_id": payment_id,
            "error": err,
            "replayed": False
        }

        c.execute(
            "UPDATE idempotency SET response_json=?,status_code=? WHERE key=?",
            (
                json.dumps(response),
                200 if status == "CONFIRMED" else 409,
                idempotency_key
            )
        )
    finally:
        c.close()

    # Send a notification after a successful order.
    if status == "CONFIRMED":
        try:
            n = downstream(
                "POST",
                f"{NOTIFICATION_URL}/api/v1/notifications",
                headers=headers,
                json_body={
                    "event_key": f"order-confirmed-{oid}",
                    "order_id": oid,
                    "message": "Your order is confirmed"
                }
            )

            if n.status_code >= 400:
                log.warning(
                    "notification failed order_id=%s status=%s",
                    oid, n.status_code
                )
        except Exception as e:
            log.warning(
                "notification unavailable order_id=%s error=%s",
                oid, type(e).__name__
            )

    return response

@app.get("/api/v1/orders/{order_id}")
def get_order(order_id:str):
 c=conn(); row=c.execute("SELECT * FROM orders WHERE order_id=?",(order_id,)).fetchone(); c.close()
 if not row: raise HTTPException(404,detail={"code":"ORDER_NOT_FOUND","message":"Order not found"})
 return dict(row)
