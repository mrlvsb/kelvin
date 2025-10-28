import json
import logging
import os
import tempfile
from typing import Dict, List, Optional

import django_rq
import requests
from serde.json import to_json

from common.summary.dto import EmbeddedFile, ReviewResult, LlmConfig
from common.summary.models import EmbeddedFile, ReviewResult, LlmConfig
from common.summary.summarizer import Summarizer
from common.serialization import dataclass_to_dict
from common.utils import download_source_to_path
from kelvin import settings

# Available file extensions and their corresponding programming languages
# If a file extension is not listed here, it will be skipped during embedding.
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".c": "c",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".rs": "rust",
    ".py": "python",
    ".java": "java",
}

SUMMARY_RESULT_FILE_NAME: str = "summary.json"


def detect_language(filename: str) -> Optional[str]:
    _, ext = os.path.splitext(filename)
    return EXTENSION_LANGUAGE_MAP.get(ext.lower())


def upload_result(submit_url: str, result: ReviewResult) -> None:
    logging.basicConfig(level=logging.DEBUG)
    session = requests.Session()

    logging.info(f"Uploading result to {submit_url}...")

    json_body = to_json(result, indent=2)
    logging.debug("Result JSON body: \n%s", json_body)

    response = session.post(
        submit_url,
        headers={"Content-Type": "application/json"},
        data=json_body,
        timeout=30,
    )

    if response.status_code != 200:
        logging.error(
            f"Failed to upload result to {submit_url}: "
            f"status_code={response.status_code}, response={response.text}"
        )
        response.raise_for_status()


def embed_source_files(source_files_path: str) -> List[EmbeddedFile]:
    embedded: List[EmbeddedFile] = []

    # Loop through downloaded files
    for root, _, files in os.walk(source_files_path):
        for file in files:
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, source_files_path)

            language = detect_language(file)
            if not language:
                logging.warning(f"Skipping file with undetected language: {relpath}")
                continue

            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            embedded_file = EmbeddedFile(
                path=relpath,
                language=language,
                content=content,
                total_lines=content.count("\n") + 1,
            )

            embedded.append(embedded_file)
            logging.debug(
                f"Embedded file: {relpath} (lang={language}, lines={embedded_file.total_lines})"
            )

    return embedded


@django_rq.job
def summary_job(submit_url, token) -> None:
    logging.basicConfig(level=logging.DEBUG)
    logging.info(f"Summarizing {submit_url}")

    with tempfile.TemporaryDirectory() as workdir:
        download_source_to_path(f"{submit_url}download?token={token}", workdir)
        embedded_files = embed_source_files(workdir)

    summary: Summarizer = Summarizer(
        model=settings.OPENAI_MODEL,
        files=embedded_files,
    )

    logging.info(f"Calling OpenAI model for review with total {len(embedded_files)} files...")
    review: ReviewResult = summary.summarize()

    upload_result(f"{submit_url}llm/result?token={token}", review)
    logging.info(f"Completed summarization for {submit_url}")


def summarize_submit(submit_config, submit_url: str, token: str) -> Optional[str]:
    llm_config: LlmConfig = LlmConfig.from_dict(submit_config)

    if not llm_config.enabled:
        return None

    return (
        django_rq.get_queue("summary").enqueue(summary_job, submit_url, token, job_timeout=180).id
    )
