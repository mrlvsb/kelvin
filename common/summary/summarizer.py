import json
import logging
import re
from typing import List

from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from openai.types.shared_params import ResponseFormatJSONObject

from common.summary.dto import EmbeddedFile, ReviewResult, Issue, Severity
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


class Summarizer:
    def __init__(self, model: str, files: List[EmbeddedFile]):
        self.model = model
        self.files = files

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
            You are a **strict, detail-oriented code reviewer** for student programming assignments.
            Your primary goal is to **analyze the provided source code for issues that directly affect correctness, memory safety, or runtime performance**.

            Each file will:
            - Be enclosed in **code fences**.
            - Include a **header comment** indicating the file name.
            - Prefix every line with a **line number** for easy reference.

            You must **only** identify issues in the following categories:
            1. **Undefined behavior**
               - Examples: use-after-free, out-of-bounds access, null dereference, uninitialized variable usage.
            2. **Memory management errors**
               - Examples: leaks, double-free, dangling pointers, incorrect malloc/free handling.
            3. **Performance inefficiencies**
               - Only if they have a **clear, measurable runtime impact** (e.g., an `O(n²)` operation in a loop where `n` can be large, redundant copies, unnecessary allocations).
            4. **Logical or operational errors**
               - Anything that causes **incorrect results, faulty control flow, or incorrect algorithmic behavior**.

            You must **NOT** report:
            - Style, naming, or formatting issues.
            - Missing error checks, unless they directly cause undefined behavior.
            - Non-critical best-practices (e.g., minor optimizations, comments, or structural preferences).
            - Hypothetical or uncertain issues — **only report what you are confident is wrong**.

            When describing code in your explanations:
            - Wrap all **variable names**, **function names**, and **code snippets** in single backticks (e.g., `buffer`, `free(ptr)`).
            - Use **exact line numbers** and **clear, factual reasoning**.
            - Avoid speculative language such as "might" or "possibly".

            Return a **single JSON object** with this structure:

            ```json
            {
                "summary": "A concise overview (3–5 sentences) describing overall correctness, key positives, and notable negatives.",
                "issues": [
                    {
                        "file": "name of the file where issue is found",
                        "severity": "critical | high | medium | low",
                        "line": "Integer line number where issue occurs",
                        "explanation": "Clear, factual description of what is wrong and why it matters (in 1–3 sentences)."
                    }
                ]
            }
            ```

            Use severity to indicate impact:
            - **critical** — Causes undefined behavior or data corruption.
            - **high** — Causes program to produce incorrect results or crash.
            - **medium** — Causes significant but not catastrophic performance or logical issues.
            - **low** — Minor inefficiencies or edge-case correctness problems.
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

            return ReviewResult(
                summary=output_json.get("summary", "No summary provided."),
                issues=[
                    Issue(
                        file=iss["file"],
                        severity=Severity(iss["severity"]),
                        line=int(iss["line"]),
                        explanation=iss["explanation"],
                    )
                    for iss in output_json.get("issues", [])
                ],
            )
        except ValueError as e:
            logging.debug(f"Raw model output: {response.choices[0].message.content}")
            raise ValueError(f"Invalid JSON in model response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse model response: {e}")
