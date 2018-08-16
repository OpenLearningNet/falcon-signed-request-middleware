import base64
import hashlib
import hmac
import json
import requests
import uuid

secret = "development".encode('utf-8')
body = json.dumps({ "example": "data" }).encode('utf-8')
request_id = str(uuid.uuid1()).encode("utf-8")

signature  = base64.b64encode(
    hmac.new(
        key=secret,
        msg=request_id + body,
        digestmod=hashlib.sha256
    ).digest()
)

headers = {
    "Content-Type": "application/json",
    "X-Auth-Signature": signature,
    "X-Auth-UUID": request_id
}

response = requests.post("http://127.0.0.1:8765/example", data=body, headers=headers)
print(response.content)
