# ShopFlow — E-commerce Microservices

**Course:** Scalable Services (SEZG583)  
**Technology:** Python, FastAPI, SQLite, REST APIs, pytest  
**Python requirement:** Python 3.11 or newer

ShopFlow is an educational e-commerce application built using four independent microservices. Each service owns its own SQLite database and communicates with other services through HTTP APIs.

The project demonstrates service decomposition, inventory concurrency control, idempotency, failure handling, compensation, and automated testing.

> This is a learning project. Payments and notifications are simulated; no real payments or emails are sent.

## 1. Services and databases

| Service | Port | Database | Responsibility |
|---|---:|---|---|
| Order Service | 8001 | `orders.db` | Creates orders and coordinates the workflow |
| Inventory Service | 8002 | `inventory.db` | Manages stock and reservations |
| Payment Service | 8003 | `payment.db` | Simulates payments and payment failures |
| Notification Service | 8004 | `notification.db` | Simulates order notifications |

Each service has its own directory, application code, dependencies, tests, and database. The databases are separate files; each service creates its required tables when its database connection is opened.

## 2. Project structure

```text
ShopFlow_Microservices_Starter/
├── services/
│   ├── order-service/
│   ├── inventory-service/
│   ├── payment-service/
│   └── notification-service/
├── scripts/
│   ├── e2e_demo.py
│   ├── concurrency_demo.py
│   ├── idempotency_demo.py
│   └── failure_demo.py
├── docs/
│   └── report-outline.md
└── README.md
```

Each service directory contains its application files, requirements, tests, and SQLite database. The exact files present may vary depending on whether the service has already been run.

## 3. Prerequisites

Install Python 3.11 or newer and ensure `py` is available in Command Prompt.

Check the installation:

```cmd
py --version
```

Open four separate Command Prompt windows, one for each service. In every window, first navigate to the project root:

```cmd
cd /d "project_root_folder"
```

Use the commands below to start each service. If its virtual environment and dependencies are already installed, you do not need to recreate the environment or reinstall the dependencies.

## 4. Start the Inventory Service

In the first Command Prompt:

```cmd
cd services\inventory-service
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set PORT=8002
set DB_PATH=inventory.db
python -m uvicorn app:app --host 127.0.0.1 --port 8002
```

Keep this window open.

## 5. Start the Payment Service

In the second Command Prompt, navigate to the project root, then run:

```cmd
cd services\payment-service
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set PORT=8003
set DB_PATH=payment.db
python -m uvicorn app:app --host 127.0.0.1 --port 8003
```

Keep this window open.

## 6. Start the Notification Service

In the third Command Prompt, navigate to the project root, then run:

```cmd
cd services\notification-service
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set PORT=8004
set DB_PATH=notification.db
python -m uvicorn app:app --host 127.0.0.1 --port 8004
```

Keep this window open.

## 7. Start the Order Service

In the fourth Command Prompt, navigate to the project root, then run:

```cmd
cd services\order-service
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
set PORT=8001
set DB_PATH=orders.db
set INVENTORY_URL=http://127.0.0.1:8002
set PAYMENT_URL=http://127.0.0.1:8003
set NOTIFICATION_URL=http://127.0.0.1:8004
python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Keep this window open as well.

**Important:** The environment variables above apply to the current Command Prompt window. Set them again whenever you start a service in a new window. Run each service from its own directory so that its default database file is created in the expected location.

## 8. Verify that the services are running

Open a fifth Command Prompt and navigate to the project root.

Check the health endpoints:

```cmd
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8004/health
```

Open the interactive API documentation:

- Order: http://127.0.0.1:8001/docs
- Inventory: http://127.0.0.1:8002/docs
- Payment: http://127.0.0.1:8003/docs
- Notification: http://127.0.0.1:8004/docs

## 9. Initialise demo inventory

Set the stock for the demo SKU to five units:

```cmd
curl -X PUT http://127.0.0.1:8002/api/v1/inventory/SKU-001 -H "Content-Type: application/json" -d "{\"quantity\":5}"
```

Expected response:

```json
{"sku":"SKU-001","quantity":5}
```

This command resets the SKU's quantity to five. Run it when you want a predictable starting point for a demonstration.

## 10. Run the demonstration scripts

Run these commands from the **project root**, with all four services running:

```cmd
services\order-service\.venv\Scripts\python.exe scripts\e2e_demo.py
services\order-service\.venv\Scripts\python.exe scripts\concurrency_demo.py
services\order-service\.venv\Scripts\python.exe scripts\idempotency_demo.py
services\order-service\.venv\Scripts\python.exe scripts\failure_demo.py
```

The scripts use HTTP requests to exercise the running services.

### Expected demonstrations

- **End-to-end workflow:** an order is confirmed, a payment succeeds, a notification is sent, and stock decreases by the ordered quantity.
- **Concurrency:** simultaneous inventory reservations must not cause the available stock to become negative.
- **Idempotency:** repeating a request with the same idempotency key and payload returns the original result; reusing the key with a different payload returns HTTP 409.
- **Payment failure:** the order becomes `FAILED`, and the inventory reservation is released through compensation.

Some demonstrations modify stock or create database records. Reset the demo stock when you need a controlled starting state.

## 11. Run the automated tests

Run each service's tests from its own directory.

For example, for Inventory:

```cmd
cd services\inventory-service
.venv\Scripts\python.exe -m pytest -q
```

Repeat from the project root for the other services:

```cmd
cd /d "C:\Users\DELL\Desktop\BITS\SEMESTER-3\SS\Assignment 1\ShopFlow_Microservices_Starter\services\payment-service"
.venv\Scripts\python.exe -m pytest -q
```

```cmd
cd /d "C:\Users\DELL\Desktop\BITS\SEMESTER-3\SS\Assignment 1\ShopFlow_Microservices_Starter\services\notification-service"
.venv\Scripts\python.exe -m pytest -q
```

```cmd
cd /d "C:\Users\DELL\Desktop\BITS\SEMESTER-3\SS\Assignment 1\ShopFlow_Microservices_Starter\services\order-service"
.venv\Scripts\python.exe -m pytest -q
```

A passing test suite may still display dependency deprecation warnings. Distinguish warnings from actual test failures and document any relevant limitations.

## 12. Main order workflow

```text
Client
  |
  v
Order Service
  |
  +----> Inventory Service: reserve stock
  |
  +----> Payment Service: simulate payment
  |
  +----> Notification Service: send mock notification
  |
  v
Order response
```

On the successful path, the order becomes `CONFIRMED`.

If payment fails after stock has been reserved, the Order Service attempts to release the reservation and marks the order `FAILED`. Notification failure should not reverse a successful payment or change a confirmed order to failed.

## 13. Business rules

1. **Inventory safety:** available stock must not become negative when reservations occur concurrently.
2. **Order idempotency:** a repeated idempotency key with the same request payload must not create another order.
3. **Payload conflict:** reusing an idempotency key with a different payload must return HTTP 409.
4. **Payment failure compensation:** a failed payment should result in a failed order and release of the reserved inventory.
5. **Payment idempotency:** repeated payment requests with the same key and payload should return the existing payment.
6. **Notification resilience:** notification failure should not undo a successful payment or a confirmed order.

Refer to the service tests and demonstration scripts for the evidence available for each rule.

## 14. API overview

| Service | Endpoint | Method | Purpose |
|---|---|---|---|
| Order | `/api/v1/orders` | POST | Create an order |
| Order | `/api/v1/orders/{order_id}` | GET | Retrieve an order |
| Inventory | `/api/v1/inventory/{sku}` | PUT | Set stock quantity |
| Inventory | `/api/v1/inventory/{sku}` | GET | Retrieve stock |
| Inventory | `/api/v1/inventory/reservations` | POST | Reserve stock |
| Inventory | `/api/v1/inventory/reservations/{reservation_id}/release` | POST | Release a reservation |
| Payment | `/api/v1/payments` | POST | Process a mock payment |
| Notification | `/api/v1/notifications` | POST | Send a mock notification |

All services also expose a `/health` endpoint. Use the Swagger pages to inspect request schemas and responses.

## 15. Limitations and future improvements

This implementation is an educational demonstration, not a production-ready e-commerce system.

Current limitations include:

- SQLite databases on the local machine.
- Synchronous HTTP communication between services.
- Mock payment and notification providers.
- Simplified compensation and failure recovery.
- No full production authentication, authorisation, or secrets-management setup.

Possible future improvements include PostgreSQL, stronger service security, durable workflow recovery, an outbox or event-driven architecture, monitoring, and integration with real external providers.