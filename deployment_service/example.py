import requests
import hmac
import hashlib
import json

key = "yoursecretvalue"

message_dict = {
    "service_name": "app",
    "container_name": "kelvin_app",
    "image": "ghcr.io/mrlvsb/kelvin:7a1db619c1a72d81d45c31970a880b1677b007c56ec175c41b244a36481f1f25",
    "commit_sha": "c8bb2dd1443a496f6a151f731c33eaca3cd6ac38",
}

message = json.dumps(message_dict).encode("utf-8")

signature = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()

url = "http://127.0.0.1:8000/"
headers = {"X-Hub-Signature-256": f"sha256={signature}", "Content-Type": "application/json"}

response = requests.post(url, headers=headers, data=message)
print(response.status_code, response.text)
