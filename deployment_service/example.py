import hashlib
import hmac
import json

import requests

key = "yoursecretvalue"

message_dict = {
    "service_name": "app",
    "container_name": "kelvin_app",
    "image": "ghcr.io/mrlvsb/kelvin:da196525cbbe8411ef3814174002b45a8cd77e11",
    "commit_sha": "da196525cbbe8411ef3814174002b45a8cd77e11",
    "healthcheck_url": "https://nginx/api/health",
}

message = json.dumps(message_dict).encode("utf-8")

signature = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()

url = "https://127.0.0.1/deployment/"
headers = {"X-Hub-Signature-256": f"sha256={signature}", "Content-Type": "application/json"}

response = requests.post(url, headers=headers, data=message, verify=False)
print(response.status_code, response.text)
