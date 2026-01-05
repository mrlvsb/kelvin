#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def format_for_github_summary(status_code, response_json):
    logs = response_json.get("logs", [])
    error_message = response_json.get("error")

    if not (200 <= status_code < 300):
        title = f"## ❌ Deployment Failed (Status: {status_code})"
        if not error_message:
            summary_lines = [f"**Error:** `{response_json.get('detail', 'Unknown error')}`"]
        else:
            summary_lines = [f"**Error:** `{error_message}`"]
    else:
        title = f"## ✅ Deployment Succeeded (Status: {status_code})"
        summary_lines = ["The deployment process completed successfully."]

    summary_lines.append("\n<details>\n\n<summary>View full deployment logs</summary>\n\n```text")
    summary_lines.extend(logs if logs else ["No logs were returned in the response."])
    summary_lines.append("```\n\n</details>\n")

    return f"{title}\n\n" + "\n".join(summary_lines)


def main():
    parser = argparse.ArgumentParser(
        description="""
        A script to send a signed deployment request to the on-premises deployment service.
        This script has NO external dependencies.
        The webhook secret can be provided via the --secret argument or, more securely,
        via the WEBHOOK_SECRET environment variable.
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--service-name",
        default="app",
        help="The name of the service in docker-compose.yml (e.g., 'app').",
    )
    parser.add_argument(
        "--container-name",
        default="kelvin_app",
        help="The exact name of the container to be deployed (e.g., 'kelvin_app').",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Full URI of the new Docker image (e.g., 'ghcr.io/mrlvsb/kelvin:latest').",
    )
    parser.add_argument(
        "--commit-sha",
        required=True,
        help="The full 40-character commit SHA for the configuration. (e.g., '42fda7e209a3e9df01a5efefb23f5a76724fa653')",
    )
    parser.add_argument(
        "--healthcheck-url",
        default="https://kelvin.cs.vsb.cz/api/v2/health",
        help="The full URL for the application's health check endpoint. (e.g., 'https://nginx/api/v2/health')",
    )

    parser.add_argument(
        "--url",
        default="https://kelvin.cs.vsb.cz/deployment/",
        help="URL of the deployment service. (e.g., 'https://127.0.0.1/deployment/')",
    )
    parser.add_argument(
        "--secret", help="The webhook secret. Overrides the WEBHOOK_SECRET environment variable."
    )
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification. Use for local development with self-signed certificates.",
    )

    args = parser.parse_args()

    is_github_env = os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("GITHUB_STEP_SUMMARY")

    secret = args.secret or os.getenv("WEBHOOK_SECRET")
    if not secret:
        print("Error: Webhook secret not found.", file=sys.stderr)
        sys.exit(1)

    message_dict = {
        "service_name": args.service_name,
        "container_name": args.container_name,
        "image": args.image,
        "commit_sha": args.commit_sha,
        "healthcheck_url": args.healthcheck_url,
    }
    message_data = json.dumps(message_dict).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message_data, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={signature}", "Content-Type": "application/json"}
    request = urllib.request.Request(args.url, data=message_data, headers=headers, method="POST")

    ssl_context = None
    if args.insecure:
        ssl_context = ssl._create_unverified_context()

    status_code = 0
    response_text = ""
    try:
        with urllib.request.urlopen(request, context=ssl_context) as response:
            status_code = response.status
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status_code = e.code
        response_text = e.read().decode("utf-8")
    except urllib.error.URLError as e:
        status_code = 503
        response_text = f'{{"logs": [], "error": "A network error occurred: {e.reason}"}}'

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError:
        response_json = {
            "logs": [response_text],
            "error": f"Invalid JSON response from server (Status: {status_code}).",
        }

    summary_content = format_for_github_summary(status_code, response_json)
    if is_github_env:
        summary_file_path = str(os.getenv("GITHUB_STEP_SUMMARY"))
        with open(summary_file_path, "a", encoding="utf-8") as f:
            f.write(summary_content + "\n")
        print("Deployment status written to GitHub Job Summary.")
    else:
        print(f"Deployment returned status {status_code}")
        print(json.dumps(response_json, indent=2))

    if not (200 <= status_code < 300):
        sys.exit(1)


if __name__ == "__main__":
    main()
