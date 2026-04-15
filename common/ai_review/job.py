import logging
import os
import tempfile
from typing import Dict, Optional, List

import django_rq
import requests
from django.conf import settings
from serde import from_dict
from serde.json import to_json

from common.ai_review.dto import (
    EmbeddedFile,
    LlmReviewPromptDTO,
    LlmConfig,
    AIReviewResult,
    SubmitReviewResultDTO,
    SuggestedCommentDTO,
    Severity,
    SuggestionState,
    AIReviewRequest,
)
from common.ai_review.llm_reviewer import AISubmitReview
from common.ai_review.openai_config import get_openai_server
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


def upload_result(submit_url: str, request: AIReviewRequest, result: AIReviewResult) -> None:
    session = requests.Session()

    # Disable SSL verification in DEBUG mode (local Docker development environment).
    #
    # EXPLANATION:
    # In the local Docker development environment (DEBUG=True), the services communicate
    # via internal Docker network names (e.g. 'https://nginx').
    # The Nginx service uses self-signed certificates for HTTPS.
    # Since these certificates are not issued by a trusted Certificate Authority (CA),
    # requests would fail with an SSL error. Disabling verification allows
    # the evaluator to download submissions and upload results in this dev environment.
    if settings.DEBUG:
        session.verify = False

    result_dto: SubmitReviewResultDTO = SubmitReviewResultDTO(
        summary=SuggestedCommentDTO(
            id=-1,
            source=None,
            line=None,
            text=result.summary,
            quality_rating=None,
            relevance_rating=None,
            severity=Severity.MEDIUM,
            state=SuggestionState.PENDING,
        ),
        suggestions=[
            SuggestedCommentDTO(
                id=-1,
                source=issue.source,
                line=issue.line,
                text=issue.explanation,
                quality_rating=None,
                relevance_rating=None,
                severity=issue.severity,
                state=SuggestionState.PENDING,
            )
            for issue in result.issues
        ],
        review_mode=request.review_mode,
        prompt_name=request.prompt_name,
        server_id=request.server_id,
        model=request.model,
    )

    json_body = to_json(result_dto, indent=2)
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
    logging.info(f"Summarizing {submit_url}")

    # Download files and embed them
    with tempfile.TemporaryDirectory() as workdir:
        download_source_to_path(f"{submit_url}download?token={token}", workdir)
        embedded_files = embed_source_files(workdir)

    # Fetch prompt configuration
    prompt_json = requests.get(f"{prompt_url}?token={token}", timeout=30)
    prompt_json.raise_for_status()
    prompt: LlmReviewPromptDTO = from_dict(LlmReviewPromptDTO, prompt_json.json())

    # Resolve the OpenAI configuration
    server = get_openai_server(llm_config.server)
    model = llm_config.model or server.models[0]

    # Check if model is available on the server
    if server.models and model not in server.models:
        logging.error(
            f"Model '{model}' is not available on server '{server.id}'. "
            f"Available models: {server.models}"
        )
        raise ValueError(f"Model '{model}' is not available on server '{server.id}'")

    summarizer: AISubmitReview = AISubmitReview(
        mode=llm_config.mode,
        files=embedded_files,
        model=model,
        prompt=prompt,
        server=server,
        language=llm_config.language,
    )

    logging.info(
        f"Calling OpenAI model for review with total {len(embedded_files)} files "
        f"(server={server.id}, model={model}, mode={llm_config.mode}, prompt={prompt.name})..."
    )

    result: AIReviewResult = summarizer.process()
    request: AIReviewRequest = summarizer.get_request()

    upload_result(f"{upload_url}?token={token}", request, result)
    logging.info(f"Completed summarization for {submit_url}")
