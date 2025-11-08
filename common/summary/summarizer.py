import json
import logging
import re
from typing import List

from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from openai.types.shared_params import ResponseFormatJSONObject

from common.summary.dto import (
    EmbeddedFile,
    ReviewResult,
    SuggestedCommentDTO,
    Severity,
    SuggestedSummaryDTO,
    SuggestionState,
)
from kelvin import settings


def enumerate_file_lines(content: str) -> str:
    return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(content.splitlines()))


def remove_comments_from_code(content: str, language: str) -> str:
    """
    Remove comments from source code based on the programming language.
    Leaves the code structure intact. Each comment is replaced with empty lines to preserve line numbers.
    """

    if language in ["c", "cpp", "java", "javascript", "typescript"]:
        content = re.sub(r"//.*", "", content)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    elif language == "python":
        content = re.sub(r"#.*", "", content)
        content = re.sub(r'"""(.*?)"""', "", content, flags=re.DOTALL)
        content = re.sub(r"'''(.*?)'''", "", content, flags=re.DOTALL)

    return content


def remove_html_entities(text: str) -> str:
    """Remove HTML entities from the given text."""
    html_entity_pattern = re.compile(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;")
    return html_entity_pattern.sub("", text)


class Summarizer:
    def __init__(self, model: str, files: List[EmbeddedFile], language: str = "English"):
        self.model = model
        self.files = files
        self.language = language

    def build_user_content(self) -> str:
        lines: List[str] = []

        for file in self.files:
            # Removing comments improves focus on code logic. Comments could be misleading.
            processed_line = remove_comments_from_code(file.content, file.language)

            # Enumerate lines for reference
            processed_line = enumerate_file_lines(processed_line)

            lines.append(f"\n### FILE: {file.path}")
            lines.append(f"```{file.language}")
            lines.append(processed_line)
            lines.append("```")

        return "\n".join(lines)

    def build_system_content(self) -> str:
        return """
            You are a **strict, detail-oriented code reviewer** evaluating student programming assignments.
            Your task is to identify real, verifiable issues that affect correctness, memory safety, or runtime performance,
            and provide clear improvement suggestions phrased in the manner of a teacher offering constructive feedback.

            For each issue you find, you will describe:
            1. **What is wrong** (referencing the exact line number).
            2. **Why it is a problem** in practical terms.
            3. **How the student should correct it**, stated as helpful guidance rather than a command.

            Your tone should be professional and instructional. You are not rewriting the code yourself.
            The suggestion should be something a teacher could "accept", "decline", or adjust when grading.

            Only report issues in the following categories:
            1. **Undefined behavior** (e.g., use-after-free, null dereference, uninitialized read, out-of-bounds access).
            2. **Memory management errors** (e.g., leaks, double free, incorrect ownership).
            3. **Performance inefficiencies** with clear runtime significance (e.g., unnecessary repeated computation).
            4. **Logical or operational errors** leading to incorrect behavior or incorrect results.

            You must **NOT** report:
            - Pure style or aesthetic issues.
            - Missing error checks, unless they directly cause undefined behavior.
            - Non-critical best-practices (e.g., minor optimizations, comments, or structural preferences).
            - Hypothetical or uncertain issues — **only report what you are confident is wrong**.

            When describing code in your explanations:
            - Wrap all **variable names**, **function names**, and **code snippets** in single backticks (e.g., `buffer`, `free(ptr)`).
            - Always use the line numbers provided.
            - Avoid vague terms like "might", "could", or "possibly" — be definitive about the issues you identify.

            Return a **single JSON object** with this structure:
            ```json
            {
                "summary": "3–5 sentences describing general correctness and main concerns.",
                "suggestions": [
                    {
                        "file": "file name",
                        "severity": "critical | high | medium | low",
                        "line": line_number,
                        "explanation": "Clear explanation of the issue and why it matters."
                    }
                ]
            }
            ```

            Severity meanings:
            - critical: causes undefined behavior or data corruption.
            - high: causes incorrect results or runtime failure.
            - medium: significant inefficiency or limited incorrect behavior.
            - low: minor correctness or efficiency improvement opportunity.
        """

    def build_translation_content(self) -> str:
        return f"""
            After analyzing, output the final JSON **entirely in {self.language}**.
            Translate only human-readable text fields (`summary` and `explanation`).
            Do not modify JSON structure, keys, field names, file names, or line numbers.
        """

    def summarize(self) -> ReviewResult:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_URL,
        )

        messages = [
            ChatCompletionSystemMessageParam(content=self.build_system_content(), role="system"),
            ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
        ]

        if self.language.lower() != "en":
            translate_prompt = ChatCompletionUserMessageParam(
                content=self.build_translation_content(), role="user"
            )
            messages.append(translate_prompt)

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            reasoning_effort="high",
            response_format=ResponseFormatJSONObject(type="json_object"),
        )

        try:
            output_text = response.choices[0].message.content
            output_json = json.loads(output_text)

            summary: str = output_json.get("summary", "No summary provided.")
            suggestions: list = output_json.get("suggestions", [])

            return ReviewResult(
                summary=SuggestedSummaryDTO(
                    id=-1, text=remove_html_entities(str(summary)), state=SuggestionState.PENDING
                ),
                suggestions=[
                    SuggestedCommentDTO(
                        id=-1,
                        source=sug["file"],
                        line=int(sug["line"]),
                        text=remove_html_entities(sug["explanation"]),
                        severity=Severity(sug["severity"]),
                        state=SuggestionState.PENDING,
                    )
                    for sug in suggestions
                ],
            )
        except ValueError as e:
            logging.debug(f"Raw model output: {response.choices[0].message.content}")
            raise ValueError(f"Invalid JSON in model response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse model response: {e}")
