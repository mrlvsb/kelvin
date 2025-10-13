from fastapi import FastAPI, Response, Security, status

from app.config import get_settings
from app.deployment import DeploymentError, DeploymentManager
from app.models import DeploymentRequest, DeploymentResponse, HealthCheckResponse
from app.security import validate_signature

app = FastAPI(
    title="Deployment Service",
    description="A Service to do on-premises deployments.",
)


@app.post(
    "/",
    summary="Trigger Deployment for a specified service",
    dependencies=[Security(validate_signature)],
    response_model=DeploymentResponse,
    responses={
        status.HTTP_200_OK: {
            "description": "Deployment succeeded",
            "content": {
                "application/json": {
                    "example": {
                        "logs": [
                            "[2025-09-01 13:45:12] [INFO] Starting deployment for commit 0474329d785bbb2c928b257f104847dc4f8f80f6",
                            "[2025-09-01 13:46:27] [INFO] Deployment successful for app:0474329d785bbb2c928b257f104847dc4f8f80f6",
                        ],
                    }
                }
            },
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Deployment failed due to an error while pulling the Docker image.",
            "content": {
                "application/json": {
                    "example": {
                        "logs": [
                            "[2025-09-01 13:45:12] [INFO] Starting deployment for commit 0474329d785bbb2c928b257f104847dc4f8f80f6",
                            "[2025-09-01 13:46:10] [INFO] Pulling new image: 0474329d785bbb2c928b257f104847dc4f8f80f6...",
                            '[2025-09-01 13:46:15] [ERROR] Failed to pull Docker image: 404 Client Error for http+docker://: Not Found ("manifest unknown")',
                        ],
                        "error": 'Failed to pull Docker image: 404 Client Error for http+docker://: Not Found ("manifest unknown")',
                    }
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Critical deployment failure, rollback may be partial, manual intervention may be required",
            "content": {
                "application/json": {
                    "example": {
                        "logs": [
                            "[2025-09-01 13:45:12] [INFO] Starting deployment for commit 0474329d785bbb2c928b257f104847dc4f8f80f6",
                            "[2025-09-01 13:46:05] [INFO] Fetching latest data from git origin...",
                            "[2025-09-01 13:46:10] [ERROR] Failed to create git worktree. Is the commit SHA valid?",
                        ],
                        "error": "Failed to create git worktree. Is the commit SHA valid?",
                    }
                }
            },
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Deployment failure, rollback completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "logs": [
                            "[2025-09-01 13:45:12] [INFO] Starting deployment for commit 0474329d785bbb2c928b257f104847dc4f8f80f6",
                            "[2025-09-01 13:46:05] [ERROR] An error occurred: Health check timed out. Initiating rollback.",
                        ],
                        "error": "Health check timed out.",
                    }
                }
            },
        },
    },
)
async def deploy(request: DeploymentRequest, response: Response):
    """
    ## Handles the deployment request after security validation.

    It instantiates and runs the DeploymentManager, returning its logs and
    a final HTTP status code reflecting the outcome.
    """

    manager = DeploymentManager(
        service_name=request.service_name,
        image=request.image,
        commit_sha=request.commit_sha,
        compose_path=get_settings().docker.compose_file_path,
        compose_env_file=get_settings().docker.compose_env_file,
        container_name=request.container_name,
        healthcheck_url=str(request.healthcheck_url),
    )
    try:
        logs = await manager.run()
        response.status_code = status.HTTP_200_OK
        return DeploymentResponse(
            logs=list(logs),
        )
    except DeploymentError as e:
        response.status_code = e.status_code
        return DeploymentResponse(logs=list(e.logs), error=e.message)


@app.get(
    "/health",
    tags=["health"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheckResponse,
)
async def get_health() -> HealthCheckResponse:
    """
    ## Perform a Health Check
    Endpoint to perform a simple healthcheck.
    """
    return HealthCheckResponse(status="OK")
