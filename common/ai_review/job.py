import logging
import os
import tempfile
from typing import Dict, Optional, List

import django_rq
import requests
from serde import from_dict
from serde.json import to_json

from common.ai_review.dto import EmbeddedFile, AIReviewResult, LlmReviewPromptDTO, LlmConfig
from common.ai_review.llm_reviewer import AISubmitReview
from common.utils import download_source_to_path

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


def detect_language(filename: str) -> Optional[str]:
    _, ext = os.path.splitext(filename)
    return EXTENSION_LANGUAGE_MAP.get(ext.lower())


def upload_result(submit_url: str, result: AIReviewResult) -> None:
    logging.basicConfig(level=logging.DEBUG)
    session = requests.Session()

    json_body = to_json(result, indent=2)
    logging.debug("Result JSON body: \n%s", json_body)

    logging.info(f"Uploading result to {submit_url}...")
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
def review_job(
    submit_url: str, upload_url: str, prompt_url: str, token: str, llm_config: LlmConfig
) -> None:
    logging.basicConfig(level=logging.DEBUG)
    logging.info(f"Summarizing {submit_url}")

    with tempfile.TemporaryDirectory() as workdir:
        download_source_to_path(f"{submit_url}download?token={token}", workdir)
        embedded_files = embed_source_files(workdir)

    # Fetch prompt configuration
    prompt_json = requests.get(f"{prompt_url}?token={token}", timeout=30)
    prompt_json.raise_for_status()
    prompt: LlmReviewPromptDTO = from_dict(LlmReviewPromptDTO, prompt_json.json())

    summarier: AISubmitReview = AISubmitReview(
        files=embedded_files,
        model=llm_config.model,
        prompt=prompt,
        language=llm_config.language,
    )

    logging.info(f"Calling OpenAI model for review with total {len(embedded_files)} files...")
    result: AIReviewResult = summarier.process()

    upload_result(f"{upload_url}?token={token}", result)
    logging.info(f"Completed summarization for {submit_url}")
