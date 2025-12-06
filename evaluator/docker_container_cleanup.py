import docker
from datetime import datetime, timezone


def delete_old_containers(n, socket_path="unix://var/run/docker.sock"):
    client = docker.APIClient(base_url=socket_path)
    containers = client.containers()
    for container in containers:
        created_at = container["Created"]
        now = datetime.now(timezone.utc).timestamp()
        elapsed = now - created_at
        if elapsed > n:
            client.kill(container["Id"])
