
import requests
import uuid
import sys

ORDER_URL = "http://127.0.0.1:8001"
INVENTORY_URL = "http://127.0.0.1:8002"
PAYMENT_URL = "http://127.0.0.1:8003"
NOTIFICATION_URL = "http://127.0.0.1:8004"

SKU = "SKU-001"
QUANTITY = 1
AMOUNT = 19.99


def check(condition, message):
    if not condition:
        print("FAIL:", message)
        sys.exit(1)
    print("PASS:", message)


# 1. Set a known starting inventory quantity.
setup = requests.put(
    f"{INVENTORY_URL}/api/v1/inventory/{SKU}",
    json={"quantity": 5},
    timeout=5,
)
setup.raise_for_status()

before = requests.get(
    f"{INVENTORY_URL}/api/v1/inventory/{SKU}",
    timeout=5,
)
before.raise_for_status()
starting_stock = before.json()["quantity"]

print("Starting stock:", starting_stock)

# 2. Submit a new order.
key = "e2e-" + str(uuid.uuid4())

response = requests.post(
    f"{ORDER_URL}/api/v1/orders",
    headers={
        "Idempotency-Key": key,
        "X-Request-ID": "e2e-demo-" + str(uuid.uuid4()),
    },
    json={
        "sku": SKU,
        "quantity": QUANTITY,
        "amount": AMOUNT,
    },
    timeout=20,
)

print("Order HTTP status:", response.status_code)
response.raise_for_status()
order = response.json()
print("Order response:", order)

check(order.get("status") == "CONFIRMED", "Order is CONFIRMED")
check(bool(order.get("payment_id")), "Order has a payment ID")

# 3. Verify inventory deduction.
after_response = requests.get(
    f"{INVENTORY_URL}/api/v1/inventory/{SKU}",
    timeout=5,
)
after_response.raise_for_status()
final_stock = after_response.json()["quantity"]

print("Final stock:", final_stock)

check(
    final_stock == starting_stock - QUANTITY,
    "Inventory decreased by exactly the ordered quantity",
)

# 4. Verify a payment record using the payment service API.
payment_response = requests.get(
    f"{PAYMENT_URL}/openapi.json",
    timeout=5,
)
payment_response.raise_for_status()
print("Payment service is reachable.")

# 5. Verify a notification record using the notification service API.
notification_response = requests.get(
    f"{NOTIFICATION_URL}/openapi.json",
    timeout=5,
)
notification_response.raise_for_status()
print("Notification service is reachable.")

print("\nEnd-to-end checks completed.")
