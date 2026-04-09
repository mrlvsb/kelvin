from openai.types.shared_params import ResponseFormatJSONSchema

# ---------------------------------------------------------------------------
# Shared field definitions
# ---------------------------------------------------------------------------

_LINE_DESCRIPTION = (
    "1-based line number of the FIRST token directly responsible for the defect. "
    "If multiple lines are involved, put the earliest causal line here and reference the others inside the explanation text."
)

_EVIDENCE_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["line", "snippet", "relevance"],
    "properties": {
        "line": {
            "type": "integer",
            "description": _LINE_DESCRIPTION,
        },
        "snippet": {"type": "string"},
        "relevance": {
            "type": "string",
            "description": "One sentence explaining why this snippet is evidence for the issue.",
        },
    },
}

_OBSERVATION_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source", "note"],
    "properties": {
        "source": {
            "type": "string",
            "description": "Filename/path this observation pertains to.",
        },
        "note": {"type": "string"},
    },
}

_STATS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sources", "total_lines", "candidate_issue_count"],
    "properties": {
        "sources": {"type": "integer"},
        "total_lines": {"type": "integer"},
        "candidate_issue_count": {"type": "integer"},
    },
}

# ---------------------------------------------------------------------------
# Candidate-issue schemas
# ---------------------------------------------------------------------------

_CANDIDATE_ISSUE_BASE_PROPS = {
    "source": {
        "type": "string",
        "description": "Name/path of the file where the issue was found.",
    },
    "category": {
        "type": "string",
        "description": "Normalized category for easier filtering in the verifier pass.",
    },
    "severity": {
        "type": "string",
        "enum": ["critical", "high", "medium", "low"],
        "description": "Estimated impact if the issue is real.",
    },
    "line": {
        "type": "integer",
        "description": _LINE_DESCRIPTION,
    },
    "title": {"type": "string"},
    "reasoning": {
        "type": "string",
        "description": (
            "Step-by-step reasoning specific to THIS issue: why you believe it's a problem, what conditions trigger it, and what you're uncertain about. "
            "Written before the conclusion."
        ),
    },
    "evidence": {
        "type": "array",
        "description": "Concrete anchors: cite specific line numbers and snippets from the enumerated source.",
        "items": _EVIDENCE_ITEM,
    },
    "why_it_matters": {"type": "string"},
    "suggested_fix": {"type": "string"},
    "confidence": {
        "type": "string",
        "enum": ["low", "medium", "high"],
    },
    "false_positive_risk": {
        "type": "string",
        "description": (
            "Specific scenario in which this issue might NOT be real. "
            "Forces explicit doubt before the verifier pass."
        ),
    },
}

_CANDIDATE_ISSUE_BASE_REQUIRED = [
    "source",
    "category",
    "severity",
    "line",
    "title",
    "reasoning",
    "evidence",
    "why_it_matters",
    "suggested_fix",
    "confidence",
    "false_positive_risk",
]

# Draft pass
_DRAFT_CANDIDATE_ISSUE = {
    "type": "object",
    "additionalProperties": False,
    "required": _CANDIDATE_ISSUE_BASE_REQUIRED,
    "properties": {**_CANDIDATE_ISSUE_BASE_PROPS},
}

# Critique pass
_CRITIQUE_CANDIDATE_ISSUE = {
    "type": "object",
    "additionalProperties": False,
    "required": [*_CANDIDATE_ISSUE_BASE_REQUIRED, "critique_note"],
    "properties": {
        **_CANDIDATE_ISSUE_BASE_PROPS,
        "critique_note": {
            "type": "string",
            "description": (
                "One sentence explaining any remaining doubt about this issue after peer review. "
                "Empty string if fully confirmed."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Response-format schemas
# ---------------------------------------------------------------------------

DRAFT_RESULT_SCHEME: ResponseFormatJSONSchema = {
    "type": "json_schema",
    "json_schema": {
        "name": "DraftResult",
        "description": (
            "Structured draft analysis: candidate issues (may include false "
            "positives) with concrete evidence so a second pass can verify and filter."
        ),
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["stats", "reasoning_trace", "observations", "candidate_issues"],
            "properties": {
                "stats": _STATS_SCHEMA,
                "reasoning_trace": {
                    "type": "string",
                    "description": (
                        "Free-form scratchpad written BEFORE populating candidate_issues. "
                        "Must follow the chain-of-thought steps defined in the system prompt."
                    ),
                },
                "observations": {
                    "type": "array",
                    "description": "Non-binding notes that might be useful to later passes.",
                    "items": _OBSERVATION_ITEM,
                },
                "candidate_issues": {
                    "type": "array",
                    "description": (
                        "Potential issues with concrete evidence. "
                        "May include uncertain items that must be filtered by the critique and verifier passes."
                    ),
                    "items": _DRAFT_CANDIDATE_ISSUE,
                },
            },
        },
    },
}

CRITIQUE_RESULT_SCHEME: ResponseFormatJSONSchema = {
    "type": "json_schema",
    "json_schema": {
        "name": "CritiqueResult",
        "description": (
            "Peer-reviewed version of the draft: false positives removed, "
            "uncertain items annotated, missed issues added."
        ),
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["stats", "reasoning_trace", "observations", "candidate_issues"],
            "properties": {
                "stats": _STATS_SCHEMA,
                "reasoning_trace": {
                    "type": "string",
                    "description": "Original trace plus critique verdicts appended.",
                },
                "observations": {
                    "type": "array",
                    "description": "Non-binding notes that might be useful to later passes.",
                    "items": _OBSERVATION_ITEM,
                },
                "candidate_issues": {
                    "type": "array",
                    "description": (
                        "Surviving issues after false positives are removed and new issues are added."
                    ),
                    "items": _CRITIQUE_CANDIDATE_ISSUE,
                },
            },
        },
    },
}

REVIEW_RESULT_SCHEME: ResponseFormatJSONSchema = {
    "type": "json_schema",
    "json_schema": {
        "name": "ReviewResult",
        "description": "A concise review summary plus a list of verified issues found in the provided files.",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "issues"],
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Overall quality assessment of the **whole codebase**. "
                        "Must cover architecture/readability/maintainability, strengths, important risks or weak areas, and a final overall quality assessment. "
                        "Do NOT enumerate individual findings in the summary."
                    ),
                },
                "issues": {
                    "type": "array",
                    "description": "Final list of verified issues.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source", "severity", "line", "explanation"],
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Name/path of the file where the issue was found.",
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low"],
                                "description": "Severity of the issue.",
                            },
                            "line": {
                                "type": "integer",
                                "description": _LINE_DESCRIPTION,
                            },
                            "explanation": {
                                "type": "string",
                                "description": (
                                    "Clearly state: what the issue is, why it is a problem, and how to fix it in one concise paragraph. "
                                    "Be specific — reference exact variable/function names in backticks. "
                                    "Avoid generic filler phrases."
                                ),
                            },
                        },
                    },
                },
            },
        },
    },
}
