import requests, uuid
url="http://127.0.0.1:8001/api/v1/orders"
body={"sku":"SKU-001","quantity":1,"amount":12.50,"simulate_failure":True}
r=requests.post(url,headers={"Idempotency-Key":"fail-"+str(uuid.uuid4())},json=body,timeout=15)
print("Payment failure test:",r.status_code,r.json())
print("Expected: FAILED order and inventory compensation.")
