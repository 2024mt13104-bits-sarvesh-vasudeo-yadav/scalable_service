# Order Service

The Order Service creates customer orders and coordinates the order workflow: it reserves stock, takes payment, confirms the order and triggers a confirmation notification.

**Port:** 8001
**Tech stack:** Python 3.11+, FastAPI, SQLite, httpx, pytest

---

## 1. Features

- **Order creation and lookup** through a REST API
- **Idempotency:** a repeated request with the same `Idempotency-Key` never creates a second order
- **Saga orchestration:** reserve stock, then take payment, then confirm the order
- **Compensation:** reserved stock is released if payment fails or a service is unavailable
- **Retries with exponential backoff and jitter** for calls to other services
- **Best-effort notifications:** a notification failure never cancels a confirmed order
- **Request tracing:** the `X-Request-ID` header is passed to every downstream service
- **Database per service:** the Order Service owns its own SQLite database (`orders.db`)

---

## 2. Folder structure

```text
order-service/
├── app.py            # Order endpoints and workflow logic
├── common.py         # Shared app setup: request-ID middleware, error handler, /health
├── test_app.py       # Automated tests (pytest)
├── requirements.txt  # Python dependencies
├── .env.example      # Example configuration
├── .gitignore
└── README.md
```

`orders.db` is created automatically the first time the service runs. It is not committed to Git.

---

## 3. Order workflow

```text
Client
  │  POST /api/v1/orders  (Idempotency-Key header)
  ▼
Order Service
  │ 1. Validate the request body
  │ 2. Check the Idempotency-Key ──► same body: return the saved response
  │                               └► different body: 409 IDEMPOTENCY_CONFLICT
  │ 3. Save the order as PENDING (orders.db)
  │
  │ 4. Reserve stock ───────────────────────────► Inventory Service
  │ 5. Process payment ─────────────────────────► Payment Service
  │
  │    Payment failed, or a service unreachable?
  │      └─► Release the reservation ───────────► Inventory Service  (compensation)
  │
  │ 6. Update the order to CONFIRMED or FAILED
  │ 7. If CONFIRMED: send a notification ───────► Notification Service
  ▼
Response: { order_id, status, payment_id, error, replayed }
```

### Order states

| Status | Meaning |
|---|---|
| `PENDING` | The order is saved and the workflow is in progress |
| `CONFIRMED` | Stock was reserved and the payment succeeded |
| `FAILED` | Inventory rejected the order, the payment failed, or a service was unavailable. Any reserved stock is released. |

---

## 4. How it works

### 4.1 Input validation
The request body is validated with Pydantic before any processing starts:
- `sku`: required, cannot be empty
- `quantity`: an integer from 1 to 10,000
- `amount`: must be greater than 0
- `simulate_failure`: optional, `false` by default. When `true`, the payment is made to fail on purpose (for testing compensation).

### 4.2 Idempotency
Every `POST /api/v1/orders` request must include an `Idempotency-Key` header.

1. The service calculates a **SHA-256 fingerprint** of the request body.
2. It opens a transaction with `BEGIN IMMEDIATE`, which locks the database so that two requests with the same key cannot both pass the check at the same time.
3. Depending on what it finds:
   - **New key:** the order is created, and the key and fingerprint are saved **in the same transaction**.
   - **Same key, same body:** the saved response is returned with `"replayed": true`. No new order is created.
   - **Same key, different body:** HTTP **409** `IDEMPOTENCY_CONFLICT` is returned.

The key is saved *before* any other service is called, so a retried request is still recognised even if the first attempt failed partway through.

### 4.3 Saga with compensation
The order is a sequence of local steps in different services. There is no shared database transaction, so each failure is handled with a compensating action:

| Failure | Result | Compensation |
|---|---|---|
| Inventory rejects the reservation (e.g. not enough stock) | `FAILED`, `INVENTORY_REJECTED` | Release the reservation (safe even if nothing was reserved) |
| Payment does not succeed | `FAILED`, `MOCK_PAYMENT_FAILED` | Release the reservation |
| Payment Service returns an error | `FAILED`, `PAYMENT_SERVICE_ERROR` | Release the reservation |
| A service cannot be reached after retries | `FAILED`, `DOWNSTREAM_UNAVAILABLE` | Best-effort release of the reservation |

The order ID is also used as the **reservation ID** and as the **payment idempotency key**. This makes repeated calls to Inventory and Payment safe.

### 4.4 Retries and timeouts
All calls to other services go through one helper, `downstream()`, which:
- uses a **1.5 second timeout**
- retries **up to 2 more times** after a timeout, a connection error or an HTTP 5xx response
- waits between attempts with **exponential backoff plus random jitter** (about 0.1s, then 0.2s, plus a small random delay) so that clients do not all retry at the same moment

### 4.5 Notifications
A notification is sent only for `CONFIRMED` orders. If the Notification Service fails or cannot be reached, the error is **logged as a warning**, and the order stays `CONFIRMED`. Each notification has an `event_key` (`order-confirmed-<order_id>`) so the Notification Service can ignore duplicates.

### 4.6 Request tracing and errors
- Every request gets an `X-Request-ID`. The client's value is used if one is sent; otherwise a new one is generated. The ID is returned in the response and passed to every downstream service, so one order can be traced end to end.
- Unexpected errors return a consistent JSON body:
  ```json
  {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred", "request_id": "..."}}
  ```

---

## 5. Database

SQLite file: `orders.db`, or the path set in `DB_PATH`. Tables are created automatically when the database is first opened.

**`orders`**

| Column | Description |
|---|---|
| `order_id` | Primary key (UUID) |
| `sku` | Product SKU |
| `quantity` | Quantity ordered |
| `amount` | Order amount |
| `status` | `PENDING`, `CONFIRMED` or `FAILED` |
| `reservation_id` | Inventory reservation ID (same as the order ID) |
| `payment_id` | Payment ID returned by the Payment Service |
| `error` | Reason for failure, if any |

**`idempotency`**

| Column | Description |
|---|---|
| `key` | The `Idempotency-Key` header value (primary key) |
| `fingerprint` | SHA-256 hash of the request body |
| `response_json` | Saved response, returned on a replay |
| `status_code` | Saved status code for the result |

---

## 6. API reference

Interactive Swagger documentation is available at **http://127.0.0.1:8001/docs** while the service is running.

### `POST /api/v1/orders`: create an order

**Headers**

| Header | Required | Description |
|---|---|---|
| `Idempotency-Key` | Yes | Unique key for this order request |
| `X-Request-ID` | No | Request ID used for tracing |

**Request body**
```json
{
  "sku": "SKU-001",
  "quantity": 1,
  "amount": 499.0,
  "simulate_failure": false
}
```

**Response: order confirmed**
```json
{
  "order_id": "<order-id>",
  "status": "CONFIRMED",
  "payment_id": "<payment-id>",
  "error": null,
  "replayed": false
}
```

**Response: payment failed (stock released)**
```json
{
  "order_id": "<order-id>",
  "status": "FAILED",
  "payment_id": "<payment-id>",
  "error": "MOCK_PAYMENT_FAILED",
  "replayed": false
}
```

**Response: replay of the same request**: the original response, with `"replayed": true`.

| HTTP status | When |
|---|---|
| 200 | Order processed (check `status` for `CONFIRMED` or `FAILED`), or a replayed response |
| 409 | `IDEMPOTENCY_CONFLICT`: the key was reused with a different request body |
| 422 | Invalid request body or missing `Idempotency-Key` header |

### `GET /api/v1/orders/{order_id}`: get an order

**Response**
```json
{
  "order_id": "<order-id>",
  "sku": "SKU-001",
  "quantity": 1,
  "amount": 499.0,
  "status": "CONFIRMED",
  "reservation_id": "<order-id>",
  "payment_id": "<payment-id>",
  "error": null
}
```
Returns **404** `ORDER_NOT_FOUND` if the order does not exist.

### `GET /health`: health check
```json
{"status": "ok", "service": "Order Service"}
```

---

## 7. Configuration

Set these environment variables, or copy the values from `.env.example`:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8001` | Port used in the start command |
| `DB_PATH` | `orders.db` | Path of the SQLite database file |
| `LOG_LEVEL` | `INFO` | Logging level |
| `INVENTORY_URL` | `http://127.0.0.1:8002` | Inventory Service base URL |
| `PAYMENT_URL` | `http://127.0.0.1:8003` | Payment Service base URL |
| `NOTIFICATION_URL` | `http://127.0.0.1:8004` | Notification Service base URL |

### Endpoints called by the Order Service

| Method | Endpoint | Body sent |
|---|---|---|
| POST | `{INVENTORY_URL}/api/v1/inventory/reservations` | `reservation_id`, `sku`, `quantity` |
| POST | `{INVENTORY_URL}/api/v1/inventory/reservations/{reservation_id}/release` | none |
| POST | `{PAYMENT_URL}/api/v1/payments` | `order_id`, `amount`, `simulate_failure`, `idempotency_key` |
| POST | `{NOTIFICATION_URL}/api/v1/notifications` | `event_key`, `order_id`, `message` |

The payment response must include `status` (`SUCCEEDED` means paid) and `payment_id`. Every call includes the `X-Request-ID` header.

---

## 8. Running the service

For orders to be processed, the services at `INVENTORY_URL`, `PAYMENT_URL` and `NOTIFICATION_URL` must be running. The `/health` endpoint works without them.

### macOS / Linux
```bash
cd services/order-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DB_PATH=orders.db
export INVENTORY_URL=http://127.0.0.1:8002
export PAYMENT_URL=http://127.0.0.1:8003
export NOTIFICATION_URL=http://127.0.0.1:8004

python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

### Windows (Command Prompt)
```cmd
cd services\order-service
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt

set DB_PATH=orders.db
set INVENTORY_URL=http://127.0.0.1:8002
set PAYMENT_URL=http://127.0.0.1:8003
set NOTIFICATION_URL=http://127.0.0.1:8004

python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

### Quick check
```bash
# Health
curl http://127.0.0.1:8001/health

# Create an order
curl -X POST http://127.0.0.1:8001/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-test-001" \
  -d '{"sku":"SKU-001","quantity":1,"amount":499.0}'

# Same key, same body: replayed response, no new order
curl -X POST http://127.0.0.1:8001/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-test-001" \
  -d '{"sku":"SKU-001","quantity":1,"amount":499.0}'

# Same key, different body: 409 IDEMPOTENCY_CONFLICT
curl -X POST http://127.0.0.1:8001/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-test-001" \
  -d '{"sku":"SKU-001","quantity":2,"amount":998.0}'

# Payment failure: order FAILED, stock released
curl -X POST http://127.0.0.1:8001/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-test-002" \
  -d '{"sku":"SKU-001","quantity":1,"amount":499.0,"simulate_failure":true}'
```

---

## 9. Running tests

```bash
cd services/order-service
python -m pytest -q
```

---

