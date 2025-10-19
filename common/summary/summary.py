import json
import logging
import os
import tempfile
from typing import Dict, List, Optional

import django_rq
import requests
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from openai.types.shared_params import ResponseFormatJSONObject

from common.models import Comment
from common.summary.models import EmbeddedFile, ReviewResult
from common.utils import download_source_to_path
from kelvin import settings

# Maps filename extension to language identifier used in code fences.
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".c": "c",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".rs": "rust",
    ".py": "python",
    ".java": "java",
}

# Maps line number -> list of Comment objects for a single file.
LineToCommentsMap = Dict[int, List[Comment]]

# Maps relative file path -> per-line comments.
FileCommentsMap = Dict[str, LineToCommentsMap]


def detect_language(filename: str) -> Optional[str]:
    _, ext = os.path.splitext(filename)
    return EXTENSION_LANGUAGE_MAP.get(ext.lower())


def download_comments(submit_url: str, token: str) -> FileCommentsMap:
    """
    Download linter/source comments for a submission.
    Returns a mapping of relative file path -> (line number -> list of Comment).
    If error occurs or no comments are found, returns an empty dict.
    """

    session = requests.Session()
    response = session.get(f"{submit_url}comments?token={token}")

    if response.status_code != 200:
        logging.error(f"Failed to download comments: {response.status_code}")
        return {}

    comments_data = response.json()
    comments = {}

    for entry in comments_data["sources"]:
        source_path = entry.get("path")
        source_comments = entry.get("comments", {})

        if not source_path or not source_comments:
            continue

        line_map: Dict[int, List[Comment]] = {}
        for line, comment_list in source_comments.items():
            for source_comment in comment_list:
                try:
                    line_no = int(line)
                except ValueError:
                    continue

                comment = Comment(
                    source=source_path,
                    line=line_no,
                    text=source_comment.get("text", ""),
                )

                line_map.setdefault(line_no, []).append(comment)

        comments[source_path] = line_map

    return comments


def upload_comments(submit_url: str, token: str, comments: Dict[str, List[Comment]]) -> None:
    # TODO: Upload comments back to the server
    return None


def embed_source_files(submit_url: str, token: str) -> List[EmbeddedFile]:
    """
    Download the submission archive and return list of EmbeddedFile objects.
    If a file's language cannot be detected, it is skipped.
    """

    embedded: List[EmbeddedFile] = []

    with tempfile.TemporaryDirectory() as workdir:
        os.chdir(workdir)
        base = os.getcwd()

        download_source_to_path(f"{submit_url}download?token={token}", ".")
        submit_comments = download_comments(submit_url, token)

        # Loop through downloaded files
        for root, _, files in os.walk(base):
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, base)

                language = detect_language(file)
                if not language:
                    logging.warning(f"Skipping file with undetected language: {relpath}")

                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Since we downloaded source comments right after evaluation, there are only linter comments
                comments = submit_comments.get(relpath, None)

                embedded_file = EmbeddedFile(
                    path=relpath,
                    language=language,
                    linter_comments=comments,
                    content=content,
                    total_lines=content.count("\n") + 1,
                )

                embedded.append(embedded_file)
                logging.debug(
                    f"Embedded file: {relpath} (lang={language}, lines={embedded_file.total_lines})"
                )

    return embedded


def build_user_content(embedded_files: List[EmbeddedFile]) -> str:
    lines: List[str] = [
        "You are given a ZIP archive expanded into the following files.",
        "Each file is presented verbatim, wrapped in a language-tagged code fence and contains linter comments if available.",
    ]

    for file in embedded_files:
        lines.append(f"\n### FILE: {file.path}")

        # Add linter info if available
        if file.linter_comments:
            for line_no, messages in sorted(file.linter_comments.items()):
                for msg in messages:
                    lines.append(f"Line {line_no}: {msg}")

        # Append file content
        lines.append(f"```{file.language}")
        lines.append(file.content.rstrip("\n"))
        lines.append("```")

    return "\n".join(lines)


def build_system_content() -> str:
    return "\n".join(
        [
            "You are strictly evaluating student-submitted source code for a programming assignments.",
            "Report only security, bug, and performance issues. AVOID duplicates and prefer root causes.",
            "Provide concise explanations and suggest fixes like a teacher would.",
            "Line numbers are relative to each code fence, starting at 1.",
            "Do not repeat issues already covered by linter comments if provided.",
            "",
            "RESPONSE FORMAT RULES (IMPORTANT):",
            "- Return ONLY a single, valid JSON object.",
            "- Do NOT include code fences or any extra text.",
            "- The JSON must follow this schema exactly:",
            "{",
            '  "summary": "string (3–6 sentences)",',
            '  "issues": [',
            "    {",
            '      "file": "string",',
            '      "start_line": 0,',
            '      "end_line": 0,',
            '      "category": "bug|security|performance",',
            '      "severity": "critical|high|medium|low",',
            '      "explanation": "string"',
            "    }",
            "  ]",
            "}",
        ]
    )


def call_openai_review(model: str, embedded_files: List[EmbeddedFile]) -> ReviewResult:
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_API_URL,
    )

    messages = [
        ChatCompletionUserMessageParam(content=build_user_content(embedded_files), role="user"),
        ChatCompletionSystemMessageParam(content=build_system_content(), role="system"),
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        reasoning_effort="high",
        response_format=ResponseFormatJSONObject(type="json_object"),
    )

    try:
        output_text = response.choices[0].message.content
        output_json = json.loads(output_text)

        return ReviewResult(
            summary=output_json.get("summary", "No summary provided."),
            issues=output_json.get("issues", []),
        )
    except Exception as e:
        raise ValueError(f"Failed to parse model response: {e}")


@django_rq.job
def summary_job(submit_url, token) -> None:
    logging.basicConfig(level=logging.DEBUG)
    logging.info(f"Summarizing {submit_url}")

    try:
        embedded_files = embed_source_files(submit_url, token)

        logging.info(f"Calling OpenAI model for review with total {len(embedded_files)} files...")
        review = call_openai_review(settings.OPENAI_MODEL, embedded_files)
    except Exception as e:
        logging.error(f"Failed to summarize submission: {e}")
        review = ReviewResult(
            summary="Error during summarization.",
            issues=[],
        )

    # TODO: Upload review results back to the server
    logging.info(f"Completed summarization for {submit_url}")
    logging.debug(f"Summary: {review.summary}")
