from pathlib import Path

from serde import json
from serde.json import from_json, to_json

import kelvin.settings
from common.ai_review.dto import OpenAIServerDTO


def ensure_config() -> Path:
    path = Path(kelvin.settings.OPENAI_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.read_text(encoding="utf-8").strip():
        return path

    servers = [
        OpenAIServerDTO(
            id="localhost",
            label="Local OpenAI Server",
            base_url="http://localhost:11434/v1",
            api_key="",
            models=["qwen3", "qwen3-coder"],
        )
    ]

    servers_json = to_json(servers, indent=4)
    path.write_text(servers_json, encoding="utf-8")

    return path


def get_openai_servers() -> list[OpenAIServerDTO]:
    path = ensure_config()
    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(
            f"{path} is empty. Please ensure it contains valid OpenAI server configurations."
        )

    try:
        parsed = from_json(list[OpenAIServerDTO], content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse {path}: {e.msg}") from e

    if not parsed:
        raise ValueError(f"{path} must define at least one server")

    return parsed


def get_openai_server(server_id: str | None) -> OpenAIServerDTO:
    servers = get_openai_servers()

    if server_id is None:
        return servers[0]

    for server in servers:
        if server.id == server_id.strip():
            return server

    raise ValueError(f"No server found with id '{server_id}'")


# Call ensure_config() at module load to create the config file if it doesn't exist
ensure_config()
