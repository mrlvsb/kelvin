import json
import subprocess
from datetime import datetime, timezone


def create_kill_command(container_id):
    return ["docker", "kill", container_id]


def delete_old_containers(n):
    data = subprocess.check_output(["docker", "ps", "--format", "json"]).decode().split("\n")[:-1]
    for container in data:
        container_data = json.loads(container)
        print(container_data)
        created_at = datetime.strptime(container_data["CreatedAt"], "%Y-%m-%d %H:%M:%S %z %Z")
        print(created_at)
        now = datetime.now(timezone.utc)
        elapsed = now - created_at
        print(elapsed.total_seconds())
        if elapsed.total_seconds() > n:
            cmd = create_kill_command(container_data["ID"])
            subprocess.run(cmd)
