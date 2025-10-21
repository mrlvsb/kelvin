# Deployment

This document outlines the end-to-end flow for automatic on-premises deployment using GitHub Actions, Docker Compose, and a FastAPI deployment endpoint, and Git worktrees to ensure that service configurations are versioned and deployed atomically with the code. It ensures minimal downtime by stopping only the target service after the new image is pre-pulled, with automatic rollback on failures.

## Workflow diagram

```mermaid
graph TD
    subgraph "A. GitHub Workflow"
        direction TB
        A1("Code Merged to Merge queue") --> A2{"GitHub <br/> Workflow <br/> triggered"};
        A2 --> A3["Build & Tag Docker Image<br/>(ghcr.io/mrlvsb/<service_name>:${{ github.sha}})"];
        A3 --> A4["Push Docker Image to Container Registry (GHCR)"];
        A4 --> A5["POST request to Deployment Endpoint<br/>(Sends image, service_name, container_name, commit_sha, and HMAC signature)"];
    end

    subgraph "B. Kelvin VM: Deployment Service"
        direction TB
        A5 -- "Request" --> B1{"Nginx Route and <br/> Validate GitHub <br/> Source IP"};
        B1 -- "Invalid IP" ----> B4["Return 401 Unauthorized"];
        B1 -- "Valid IP" ----> B2["FastAPI Endpoint (/deployment/)"];
        B2 --> B3{"Validate HMAC <br/>Signature"};
        B3 -- "Invalid Signature" ----> B4;
        B3 -- "Valid Signature" ----> B5["Instantiate DeploymentManager<br/>(Passes all request parameters)"];
        B5 -- "Output (stdout/stderr)" --> B6["Stream Logs & Return Final HTTP Status<br/>(200 OK, 400, 500, or 502)"];
    end

    subgraph "C. Kelvin VM: Deployment Logic (DeploymentManager)"
        direction TB
        B5 --> C1["Create Temporary Git Worktree for new commit_sha"];
        C1 -- Fails --> C3["Exit & Return 500 Internal Server Error"];
        C1 -- Succeeds --> C2["Get Current Image ID for Rollback<br/>(docker.from_env)"];
        C2 --> C4["Pull New Docker Image<br/>(docker.from_env)"];
        C4 -- Fails --> C5["Exit & Return 400 Bad Request"];
        C4 -- Succeeds --> C6["Swap Service: Stop old container (using stable compose file) & Start new container (using worktree's compose file)"];
        C6 -- Fails --> C9["Rollback: Restart service with previous image ID and stable compose file"];
        C6 -- Succeeds --> C7{"Health Check"};
        C7 -- Unhealthy --> C9;
        C9 --> C10["Exit & Return 502 Bad Gateway"];
        C7 -- Healthy --> C8["Update Stable Git Repo to new commit_sha (git reset --hard)"];
        C8 --> C11["Cleanup: Remove old image & temporary worktree"];
        C11 --> C12["Exit & Return 200 OK"];
    end

    subgraph "D. GitHub Workflow"
      direction TB
      B4 -- "4xx/5xx Response" --> D1["Workflow Fails"];
      B6 --> D2{"Process <br/> Response"};
      D2 -- "4xx or 5xx Error" --> D1;
      D2 -- "200 OK" --> D3["Deployment Succeeded"];
      D3 --> D4["Update 'latest' tag in Container Registry (GHCR) to point to new image"];
      D4 --> D5["Workflow Succeeds"];
    end
```

## Steps Description

### A. Merge Queue Trigger

- A pull request merged through the repository’s merge queue triggers the deployment workflow.

### B. GitHub Workflow

#### 1. **Build & Push Docker Image**

- Builds the Docker image and tags it with the unique commit SHA: `ghcr.io/mrlvsb/<service_name>:${{ github.sha }}`.
- Pushes the tagged image to the GitHub Container Registry (GHCR). At this point, the latest tag is not touched.

#### 2. **Call Deployment Endpoint**

- Computes an HMAC signature over the GitHub event payload using `WEBHOOK_SECRET`.
- Sends a `POST` request to the Kelvin VM’s `/deployment/` with the `X-Hub-Signature-256` header. The JSON body includes:

   - service_name: The service to target in docker-compose.yml.
   - container_name: The specific container name for health checks and state capture.
   - image: The full image URI.
   - commit_sha: The Git commit hash representing the desired configuration state.
- The workflow fails immediately on any non-200 response.


### C. Kelvin VM: Deployment Service

The deployment endpoint is a small, secure, and separate FastAPI service. It is designed with a clear separation of concerns and runs within its own Docker container.

#### 1. **Reverse Proxy (Nginx) & IP Whitelisting**

The deployment service depends on a Reverse Proxy (Nginx), which acts as the single public-facing entry point on the server. This proxy is configured with a firewall or IP allowlist to ensure that only requests originating from official GitHub runner IP addresses are accepted. If a request comes from an unauthorized IP, it is immediately blocked with a `401 Unauthorized` status. For valid requests, Nginx routes them internally to the Deployment Service.

#### 2. **Deployment Service Container & HMAC Validation**

This lightweight container runs the FastAPI endpoint. To manage deployments, it uses the `Docker-out-of-Docker` (DooD) concept: the host's Docker socket (`/var/run/docker.sock`) is mounted as a volume into this container. This allows script to issue `docker` and `docker compose` commands directly to the host's Docker daemon. As a second layer of security, this service validates the HMAC signature from the request header. If the signature is invalid, it returns a `401 Unauthorized` error.

#### 3. **Invoke Deployment Logic**

Upon successful validation, the service instantiates a `DeploymentManager`, passing it the request parameters. This class encapsulates the entire deployment and rollback logic.

#### 4. **Stream Logs & Return Status**

The service captures all logs generated by the DeploymentManager and includes them in the final HTTP response. This provides full visibility for debugging and returns the final status code from the process (e.g., `200`, `400`, `500`, `502`).


### D. Kelvin VM: Deployment Script

The core of the process uses a temporary Git worktree to ensure the deployment is atomic and that the configuration (e.g., `docker-compose.yml`) perfectly matches the deployed code version.

#### **1. Create Temporary Git Worktree**

To avoid disrupting the stable configuration, the manager first creates a temporary directory and checks out the code from the specified commit_sha into it using git worktree add. This isolates the new configuration files for the upcoming deployment.

#### **2. Capture Rollback State & Pull New Image**


- The logic inspects the currently running application container to get its exact image ID. This ID is stored as a reliable rollback target.

- It then pulls the new image from the container registry. If the pull fails (e.g., image not found), it exits with a 400 Bad Request status without affecting the running service.


#### **3. Swap Service**

- The service swap is performed using two different configurations:
    1. **Stop**: `docker compose stop <service_name>` is run against the stable (current) `docker-compose.yml` file.
    2. **Start**: `docker compose up -d --no-deps <service_name>` is run against the `docker-compose.yml` file in the temporary Git worktree. The new image tag is passed as an environment variable (`<SERVICE_NAME>_IMAGE_TAG`) to the command.

#### **4. Health Check**

The manager performs an active health check by repeatedly sending HTTP GET requests to a specified `healthcheck_url`. It continuously polls this endpoint until it receives a 200 OK status code, which indicates the service is ready. If the health check times out, it triggers a rollback.

#### **5. Rollback (on Failure)**

- If the service fails to start or the health check times out, a FallbackError is raised.

- The logic initiates a rollback by calling the swap logic again, but in reverse: it uses the stable `docker-compose.yml` and overrides the image tag with the previous image ID captured in step 2.

- The workflow fails with a 502 Bad Gateway response, indicating a successful rollback.

#### **6. Finalize & Cleanup (on Success)**

- If healthy:

    - The deployment is now considered successful. To make the state persistent, the stable Git repository directory is updated to the new state using `git reset --hard <commit_sha>`.

    - The old Docker image is removed to free up resources.

    - The temporary Git worktree is removed.

    - The service returns 200 OK.

### D. GitHub Workflow

The GitHub Actions workflow waits for the HTTP response from the Kelvin Deployment Service.

- A `200 OK` response confirms a successful deployment. The workflow proceeds to update the `latest` tag in GHCR to point to the newly deployed image and marks the run as successful.

- Any other status code (`4xx` or `5xx`) marks the workflow as failed. The detailed logs returned from the deployment service are printed to the workflow output for diagnostics.
