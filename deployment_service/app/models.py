from pydantic import BaseModel, Field
from typing import Annotated


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
    image_sha: str = Field(
        ...,
        pattern=r"^[a-fA-F0-9]{40}$",
        description="The unique 40-character git commit SHA-1 tag of the new Docker image.",
        examples=["ffac537e6cbbf934b08745a378932722df287a53"],
    )
    commit_sha: str = Field(
        ...,
        pattern=r"^[a-fA-F0-9]{40}$",
        description="The full commit SHA to check out for the configuration. This is the source of truth.",
        examples=["ffac537e6cbbf934b08745a378932722df287a53"],
    )


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
                decription="Error message if the deployment failed; omitted on success.",
            ),
        ]
        | None
    ) = None


class HealthCheckResponse(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"
