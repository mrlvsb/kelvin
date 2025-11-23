import json
import logging
import re
from typing import List

from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from openai.types.shared_params import ResponseFormatJSONObject
from pycountry import languages

from common.ai_review.dto import (
    EmbeddedFile,
    AIReviewResult,
    Severity,
    SubmitSummary,
    SuggestedCommentDTO,
    SuggestionState,
)
from common.ai_review.dto import LlmReviewPromptDTO
from kelvin import settings


def enumerate_file_lines(content: str) -> str:
    return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(content.splitlines()))


def remove_html_entities(text: str) -> str:
    """Remove HTML entities from the given text."""
    html_entity_pattern = re.compile(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;")
    return html_entity_pattern.sub("", text)


class AISubmitReview:
    def __init__(
        self,
        files: List[EmbeddedFile],
        model: str,
        prompt: LlmReviewPromptDTO,
        language: str = "cs",
    ):
        self.files = files
        self.model = model
        self.prompt = prompt
        self.language = language

    def build_user_content(self) -> str:
        lines: List[str] = []

        for file in self.files:
            # Enumerate lines for reference
            processed_line = enumerate_file_lines(file.content)

            lines.append(f"\n### FILE: {file.path}")
            lines.append(f"```{file.language}")
            lines.append(processed_line)
            lines.append("```")

        return "\n".join(lines)

    def build_translation_content(self) -> str:
        lang = languages.get(alpha_2=self.language)

        return f"""
            After analyzing, output the final JSON **entirely in {lang.name}**.
            Translate only human-readable text fields (`summary` and `explanation`).
            Do not modify JSON structure, keys, field names, file names, or line numbers.
        """

    def process(self) -> AIReviewResult:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_URL,
        )

        messages = [
            ChatCompletionSystemMessageParam(content=self.prompt.text, role="system"),
            ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
        ]

        # Since prompt is written in English, we need to translate when the output language is not English
        if self.language.lower() != "en":
            translate_prompt = ChatCompletionSystemMessageParam(
                content=self.build_translation_content(), role="system"
            )
            messages.append(translate_prompt)

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            response_format=ResponseFormatJSONObject(type="json_object"),
        )

        try:
            output_text = response.choices[0].message.content
            output_json = json.loads(output_text)

            summary: str = output_json.get("summary", "No summary provided.")
            suggestions: list = output_json.get("suggestions", [])

            return AIReviewResult(
                summary=SubmitSummary(
                    id=-1,
                    text=remove_html_entities(summary),
                    rating=None,
                    model=self.model,
                    prompt_id=self.prompt.id,
                    state=SuggestionState.PENDING,
                ),
                suggestions=[
                    SuggestedCommentDTO(
                        id=-1,
                        source=sug["file"],
                        line=int(sug["line"]),
                        text=remove_html_entities(sug["explanation"]),
                        rating=None,
                        model=self.model,
                        prompt_id=self.prompt.id,
                        severity=Severity(sug["severity"]),
                        state=SuggestionState.PENDING,
                    )
                    for sug in suggestions[:200]
                ],
                prompt_id=self.prompt.id,
                model=self.model,
            )
        except ValueError as e:
            logging.debug(f"Raw model output: {response.choices[0].message.content}")
            raise ValueError(f"Invalid JSON in model response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse model response: {e}")
