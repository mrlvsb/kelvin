#!/usr/bin/env python3
import http.client
import sys

SERVICE_HOST = "localhost"  # Or your service hostname
SERVICE_PORT = 9000  # Port your FastAPI app is running on
HEALTH_ENDPOINT = "/health"  # Endpoint you want to check

try:
    conn = http.client.HTTPConnection(SERVICE_HOST, SERVICE_PORT, timeout=5)
    conn.request("GET", HEALTH_ENDPOINT)
    response = conn.getresponse()

    if 200 <= response.status < 300:
        sys.exit(0)  # Healthy
    else:
        sys.exit(1)  # Unhealthy
except Exception:
    sys.exit(1)
finally:
    conn.close()
