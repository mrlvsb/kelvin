import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

IMAGE_PATTERN = re.compile(
    r"^(?P<repository>[\w.\-_]+((?::\d+|)(?=/[a-z0-9._-]+/[a-z0-9._-]+))|)"
    r"(?:/|)"
    r"(?P<image>[a-z0-9.\-_]+(?:/[a-z0-9.\-_]+|))"
    r":(?P<tag>[\w.\-_]{1,127})$"
)


class DeploymentRequest(BaseModel):
    """Defines the expected JSON body for the /deploy endpoint."""

    service_name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$",
        description="The name of the service in docker-compose.yml to be deployed.",
        examples=["app"],
    )
    container_name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$",
        description="The name of the container to be deployed.",
        examples=["project_app"],
    )
    image: dict[str, str] = Field(
        ...,
        description="The new Docker image (repository is optional, image and tag are required).",
        examples=["ghcr.io/mrlvsb/kelvin:latest"],
    )
    commit_sha: str = Field(
        ...,
        pattern=r"^[a-fA-F0-9]{40}$",
        description="The full commit SHA to check out for the configuration. This is the source of truth.",
        examples=["ffac537e6cbbf934b08745a378932722df287a53"],
    )

    @field_validator("image", mode="before")
    @classmethod
    def parse_image(cls, value: str) -> dict[str, str]:
        m = IMAGE_PATTERN.match(value)
        if not m:
            raise ValueError("Invalid image format. Expected [repository/]<image>:<tag>.")
        parts = m.groupdict()
        parts["image"] = parts["image"].rstrip("/")
        return parts


class DeploymentResponse(BaseModel):
    """Defines the structured JSON response for the deployment endpoint."""

    logs: Annotated[
        list[str],
        Field(
            ...,
            description="Ordered log messages from the deployment process.",
        ),
    ]
    error: (
        Annotated[
            str,
            Field(
                description="Error message if the deployment failed; omitted on success.",
            ),
        ]
        | None
    ) = None


class HealthCheckResponse(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"
