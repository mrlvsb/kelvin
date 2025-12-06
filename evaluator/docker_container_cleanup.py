import docker
from datetime import datetime, timezone


# Deletes Docker containers that have been running for more than max_lifetime seconds.
def delete_old_containers(max_lifetime: int, socket_path="unix://var/run/docker.sock"):
    client = docker.APIClient(base_url=socket_path)
    containers = client.containers()
    for container in containers:
        created_at = container["Created"]
        now = datetime.now(timezone.utc).timestamp()
        elapsed = now - created_at
        if elapsed > max_lifetime:
            client.kill(container["Id"])
