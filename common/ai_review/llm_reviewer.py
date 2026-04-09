import json
import logging
import re
from time import time
from typing import List, Tuple, TypeVar, Dict, Any, Optional

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionAssistantMessageParam,
)
from serde import from_dict, to_dict

from common.ai_review.dto import (
    EmbeddedFile,
    OpenAIServerDTO,
    ReviewMode,
    AIReviewResult,
    DraftResult,
    ReviewIssue,
    AIReviewRequest,
)
from common.ai_review.dto import LlmReviewPromptDTO
from common.ai_review.prompt import DECISIVE_PROMPT, JUSTIFICATION_PROMPT, CRITIQUE_PROMPT
from common.ai_review.scheme import (
    REVIEW_RESULT_SCHEME,
    DRAFT_RESULT_SCHEME,
    CRITIQUE_RESULT_SCHEME,
)

# Generic return type for typed JSON parsing.
# We use a TypeVar so `parse_json(..., target_type=ReviewResult)` is typed as
# returning `ReviewResult` (and similarly for `DraftResult`) instead of `Any`.
# This keeps call sites type-safe and avoids repetitive casts.
ResultType = TypeVar("ResultType")


def enumerate_file_lines(content: str) -> str:
    return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(content.splitlines()))


def remove_html_entities(text: str) -> str:
    """Remove HTML entities from the given text."""
    html_entity_pattern = re.compile(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;")
    return html_entity_pattern.sub("", text)


class AISubmitReview:
    def __init__(
        self,
        mode: ReviewMode,
        files: List[EmbeddedFile],
        model: str,
        prompt: LlmReviewPromptDTO,
        server: OpenAIServerDTO,
        language: str | None,
    ):
        self.mode = mode
        self.files = files
        self.model = model
        self.prompt = prompt
        self.language = language
        self.server = server
        self.total_output_tokens = 0
        self.total_input_tokens = 0
        self.client = OpenAI(
            api_key=server.api_key,
            base_url=server.base_url,
        )

    def process(self) -> AIReviewResult:
        logging.info("Starting analysis on %d files...", len(self.files))
        start_time = time()

        if self.mode == ReviewMode.ZERO_SHOT:
            review_result: AIReviewResult = self.run_zero_shot_analysis()
        elif self.mode == ReviewMode.THINKING:
            review_result: AIReviewResult = self.run_thinking_analysis()
        else:
            draft_result: DraftResult = self.run_draft_analysis()
            critique_result: DraftResult = self.run_critique_analysis(draft_result)
            review_result: AIReviewResult = self.run_review_analysis(critique_result)

        # Post-process: normalize filenames to match known paths exactly
        review_result = self.normalize_issue_filenames(review_result)

        total_elapsed_seconds: float = time() - start_time
        logging.info(
            "Source code review completed. Total elapsed time: %.2f seconds. Issues found: %d. Total tokens — input: %d, output: %d",
            total_elapsed_seconds,
            len(review_result.issues),
            self.total_input_tokens,
            self.total_output_tokens,
        )

        return review_result

    def get_request(self) -> AIReviewRequest:
        return AIReviewRequest(
            review_mode=self.mode,
            model=self.model,
            server_id=self.server.id,
            prompt_name=self.prompt.name,
        )

    # -------------------------
    # Pipeline steps
    # -------------------------

    # Zero shot
    def run_zero_shot_analysis(self):
        elapsed, response_text = self.timed_chat_completion(
            step_name="Zero-shot analysis",
            messages=[
                ChatCompletionSystemMessageParam(
                    content=self.build_translated_prompt(self.prompt.text), role="system"
                ),
                ChatCompletionSystemMessageParam(content=JUSTIFICATION_PROMPT, role="system"),
                ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
            ],
            response_format=REVIEW_RESULT_SCHEME,
            temperature=0.1,
        )

        review_result: AIReviewResult = self.parse_json(
            step_name="Zero-shot analysis",
            raw_text=response_text,
            target_type=AIReviewResult,
        )

        logging.info(
            "One-shot review analysis completed in %d seconds. Final issues count: %d",
            elapsed,
            len(review_result.issues),
        )

        return review_result

    # Thinking
    def run_thinking_analysis(self):
        thinking_kwargs: Dict[str, Any] = {
            "reasoning_effort": "medium",
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        }

        elapsed, response_text = self.timed_chat_completion(
            step_name="Thinking analysis",
            messages=[
                ChatCompletionSystemMessageParam(
                    content=self.build_translated_prompt(self.prompt.text), role="system"
                ),
                ChatCompletionSystemMessageParam(content=JUSTIFICATION_PROMPT, role="system"),
                ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
            ],
            response_format=REVIEW_RESULT_SCHEME,
            temperature=0.1,
            timeout=60 * 5,
            extra_kwargs=thinking_kwargs,
        )

        review_result: AIReviewResult = self.parse_json(
            step_name="Thinking analysis",
            raw_text=response_text,
            target_type=AIReviewResult,
        )

        logging.info(
            "Thinking analysis completed in %d seconds. Final issues count: %d",
            elapsed,
            len(review_result.issues),
        )

        return review_result

    # Chain of thought
    def run_draft_analysis(self):
        elapsed, draft_text = self.timed_chat_completion(
            step_name="Draft analysis",
            messages=[
                ChatCompletionSystemMessageParam(content=self.prompt.text, role="system"),
                ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
            ],
            response_format=DRAFT_RESULT_SCHEME,
            temperature=0.3,
        )

        draft_result: DraftResult = self.parse_json(
            step_name="Draft analysis",
            raw_text=draft_text,
            target_type=DraftResult,
        )

        logging.info(
            "Draft analysis completed in %d seconds. Identified %d candidate issues.",
            elapsed,
            len(draft_result.candidate_issues),
        )

        return draft_result

    def run_critique_analysis(self, draft_result: DraftResult):
        draft_content: str = f"""
            Draft analysis to critique:
            {json.dumps(to_dict(draft_result), indent=2)}
        """

        final_prompt: str = """
            Challenge every candidate issue. Remove false positives, annotate uncertain ones.
            Output the updated DraftResult JSON.
        """

        elapsed, critique_text = self.timed_chat_completion(
            step_name="Critique analysis",
            messages=[
                ChatCompletionSystemMessageParam(content=CRITIQUE_PROMPT, role="system"),
                ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
                ChatCompletionAssistantMessageParam(content=draft_content, role="assistant"),
                ChatCompletionUserMessageParam(content=final_prompt, role="user"),
            ],
            response_format=CRITIQUE_RESULT_SCHEME,
            temperature=0.2,
        )

        critique_result: DraftResult = self.parse_json(
            step_name="Critique analysis",
            raw_text=critique_text,
            target_type=DraftResult,
        )

        logging.info(
            "Critique completed in %d seconds. Surviving issues: %d (was %d after draft).",
            elapsed,
            len(critique_result.candidate_issues),
            len(draft_result.candidate_issues),
        )

        return critique_result

    def run_review_analysis(self, critique_result: DraftResult) -> AIReviewResult:
        critique_content: str = f"""
            Peer-reviewed candidate issues:
            {json.dumps(to_dict(critique_result), indent=2)}
        """

        final_prompt: str = (
            "Verify the surviving issues against the code. "
            "Keep only deterministic, real issues and output the final ReviewResult JSON. "
        )

        elapsed, review_text = self.timed_chat_completion(
            step_name="Review analysis",
            messages=[
                ChatCompletionSystemMessageParam(content=DECISIVE_PROMPT, role="system"),
                ChatCompletionUserMessageParam(content=self.build_user_content(), role="user"),
                ChatCompletionAssistantMessageParam(content=critique_content, role="assistant"),
                ChatCompletionUserMessageParam(
                    content=self.build_translated_prompt(final_prompt), role="user"
                ),
            ],
            response_format=REVIEW_RESULT_SCHEME,
            temperature=0.1,
        )

        review_result: AIReviewResult = self.parse_json(
            step_name="Review analysis",
            raw_text=review_text,
            target_type=AIReviewResult,
        )

        logging.info(
            "Review analysis completed in %d seconds. Final issues count: %d",
            elapsed,
            len(review_result.issues),
        )

        return review_result

    # -------------------------
    # Utility
    # -------------------------

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

    def build_translated_prompt(self, prompt: str) -> str:
        if self.language:
            prompt += f"""
                Produce final review in {self.language} language.
                All technical terms, code snippets or function/variables names must preserve exactly as-is.
             """

        return prompt

    def timed_chat_completion(
        self,
        step_name: str,
        messages: List[ChatCompletionMessageParam],
        response_format,
        temperature: float,
        timeout: int = 180,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, str]:
        step_start_time: float = time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            timeout=180,
            **(extra_kwargs or {}),
        )

        elapsed_seconds: float = time() - step_start_time
        message_content: str | None = response.choices[0].message.content

        input_tokens: int = response.usage.prompt_tokens
        output_tokens: int = response.usage.completion_tokens
        logging.info(
            "Step '%s' tokens — input: %d, output: %d",
            step_name,
            input_tokens,
            output_tokens,
        )
        self.total_input_tokens = self.total_output_tokens + input_tokens
        self.total_output_tokens = self.total_output_tokens + output_tokens

        if message_content is None:
            raise ValueError(f"{step_name} returned empty message content.")

        return elapsed_seconds, message_content

    def parse_json(
        self, step_name: str, raw_text: str, target_type: type[ResultType]
    ) -> ResultType:
        try:
            parsed_json: Dict[str, Any] = json.loads(raw_text)
        except Exception as exception:
            logging.error("Failed to parse %s: %s", step_name, exception)
            logging.info("Raw model response content: %s", raw_text)
            raise

        try:
            typed_result: ResultType = from_dict(target_type, parsed_json)
            return typed_result
        except Exception as exception:
            logging.error(
                "Failed to convert %s into %s: %s", step_name, target_type.__name__, exception
            )
            logging.info("Parsed JSON payload: %s", json.dumps(parsed_json, indent=2))
            raise

    def normalize_issue_filenames(self, review_result: AIReviewResult) -> AIReviewResult:
        """Ensure every issue's file field exactly matches one of the embedded file paths.

        The LLM sometimes shortens, alters, or slightly misspells filenames.
        We match each returned name against the known paths using a simple
        longest-suffix strategy: pick the known path whose suffix best matches
        the returned value (case-insensitive). If no match is found and there
        is only a single embedded file, that file is used as an unambiguous
        fallback. Otherwise, the original value is kept and a warning is logged.

        THIS IS NIGHTMARE... BUT I SPENT WHOLE DAY TRY TO FIX THIS. STUPID LLMS
        """
        known_paths: List[str] = [f.path for f in self.files]

        def best_match(target_issue: ReviewIssue, name: str) -> str:
            if name in known_paths:
                return name

            # If there is only one embedded file, it must be the one :D
            if len(known_paths) == 1:
                return known_paths[0]

            name_normalized = name.replace("\\", "/").lower()

            # Try suffix match: pick the known path that ends with the returned name
            candidates = [
                p for p in known_paths if p.replace("\\", "/").lower().endswith(name_normalized)
            ]
            if len(candidates) == 1:
                return candidates[0]

            # Try prefix match (model may have stripped a leading directory)
            candidates = [
                p for p in known_paths if name_normalized.endswith(p.replace("\\", "/").lower())
            ]
            if len(candidates) == 1:
                return candidates[0]

            # Try to match by basename only (model may have stripped directories or returned only the filename)
            name_base = name_normalized.rsplit("/", 1)[-1]
            candidates = [
                p
                for p in known_paths
                if p.replace("\\", "/").lower().rsplit("/", 1)[-1] == name_base
            ]
            if len(candidates) == 1:
                return candidates[0]

            # Try to ignore common "copy" suffixes. (models retrieves "foo.c (1)" and returns it only a "foo.c")
            def strip_copy_suffix(path: str) -> str:
                base = path.replace("\\", "/").lower().rsplit("/", 1)[-1]
                return re.sub(r"\s*\(\d+\)(?=\.[^.]+$)", "", base)

            candidates = [p for p in known_paths if strip_copy_suffix(p) == name_base]
            if len(candidates) == 1:
                return candidates[0]

            # We failed... Let AI rule the world!
            logging.warning(
                "Could not normalize issue %s filename %r to any known path %s",
                target_issue.location(),
                name,
                known_paths,
            )

            return name

        for issue in review_result.issues:
            original = issue.source
            issue.source = best_match(issue, original)

            if issue.source != original:
                logging.info(
                    "Normalized issue %s filename %r --> %r",
                    issue.location(),
                    original,
                    issue.source,
                )

        return review_result
