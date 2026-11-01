import requests, uuid
key="idem-"+str(uuid.uuid4()); url="http://127.0.0.1:8001/api/v1/orders"
body={"sku":"SKU-001","quantity":1,"amount":9.99}
for label in ("first","repeat"):
 r=requests.post(url,headers={"Idempotency-Key":key},json=body,timeout=15)
 print(label,r.status_code,r.json())
r=requests.post(url,headers={"Idempotency-Key":key},json={**body,"quantity":2},timeout=5)
print("same key, different payload:",r.status_code,r.text)
