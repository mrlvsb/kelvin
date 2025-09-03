#!/usr/bin/env python3
import socket
import struct
import sys

SERVICE_SOCKET_PATH = "/socket/kelvin.sock"
HEALTH_ENDPOINT = "/api/health"

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(SERVICE_SOCKET_PATH)

# Required WSGI variables for Django
env_vars = [
    ("REQUEST_METHOD", "GET"),
    ("PATH_INFO", HEALTH_ENDPOINT),
    ("SERVER_NAME", "localhost"),
    ("SERVER_PORT", "80"),
    ("REQUEST_URI", HEALTH_ENDPOINT),
]

# Build uwsgi packet
data = b""
for key, value in env_vars:
    key_bytes = key.encode()
    value_bytes = value.encode()
    data += struct.pack("<H", len(key_bytes)) + key_bytes
    data += struct.pack("<H", len(value_bytes)) + value_bytes

packet = struct.pack("<BHB", 0, len(data), 0) + data

try:
    sock.send(packet)
    response = sock.recv(4096)
    sock.close()

    resp_text = response.decode("utf-8", errors="ignore")
    if resp_text.startswith("HTTP/") and "200" in resp_text.splitlines()[0]:
        sys.exit(0)  # healthy
    else:
        sys.exit(1)  # unhealthy
except Exception:
    sys.exit(1)
