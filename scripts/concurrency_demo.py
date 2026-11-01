import concurrent.futures, requests, uuid
inv="http://127.0.0.1:8002"
requests.put(inv+"/api/v1/inventory/SKU-RACE",json={"quantity":5}).raise_for_status()
def reserve(i):
 return requests.post(inv+"/api/v1/inventory/reservations",json={"reservation_id":str(uuid.uuid4()),"sku":"SKU-RACE","quantity":1},timeout=15).status_code
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
 results=list(pool.map(reserve,range(20)))
print("Requests:",len(results),"successful:",results.count(200),"rejected:",len(results)-results.count(200))
print("Final stock:",requests.get(inv+"/api/v1/inventory/SKU-RACE").json())
