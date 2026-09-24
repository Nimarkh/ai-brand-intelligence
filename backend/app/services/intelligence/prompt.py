"""Prompt construction for Ask Intelligence. Routes do not build prompts."""

from __future__ import annotations

import json
from typing import Any

from app.services.ai.models import AIRequest
from app.services.intelligence.models import MAX_PROMPT_CHARS, HistoryTurn, QuestionIntent
from app.services.intelligence.safety import fit_history_lines

ANALYST_OPENING = "You are the intelligence analyst inside this application."

SYSTEM_PROMPT = f"""{ANALYST_OPENING}

Answer only using the supplied audit context.

Do not invent:
- scores
- findings
- recommendations
- queries
- responses
- companies
- facts

If the supplied context does not contain enough information to answer, say so explicitly.

Distinguish between:
- persisted facts
- calculated metrics
- recommendations
- interpretation

Do not claim that an action has been performed unless the system actually performed it.
You do not have internet access.
Do not claim to have searched Google, ChatGPT, Perplexity, Gemini, or any other outside system.

You are not a general-purpose assistant. If the question is unrelated to this audit
(general knowledge, jokes, stories, or unrelated code), say that you are focused on
analyzing this audit's brand intelligence data and that the audit context is not
enough to answer that question.

AI-generated explanations are interpretations of stored data, not new measurements.
"""


def build_provider_request(
    *,
    question: str,
    brand_name: str,
    intent: QuestionIntent,
    context_payload: dict[str, Any],
    history: list[HistoryTurn],
) -> AIRequest:
    """Build the provider request. The client never supplies the system prompt."""
    context_json = json.dumps(
        context_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    header = (
        f"Brand: {brand_name}\n"
        f"Intent: {intent.value}\n"
        f"Question: {_single_line(question)}\n\n"
        "The JSON below is the only audit context you may use. "
        "Values marked persisted_score are stored measurements. "
        "Values marked calculated_metric are derived from stored rows. "
        "Values marked recommendation are stored recommendations, not actions already taken.\n\n"
        f"CONTEXT_JSON:\n{context_json}\n"
    )
    history_lines = [f"{turn.role}: {turn.content}" for turn in history]
    history_lines = fit_history_lines(history_lines, reserved_chars=len(header) + 80)
    if len(header) > MAX_PROMPT_CHARS:
        header = header[: MAX_PROMPT_CHARS - 1] + "…"
        history_lines = []
    history_block = "\n".join(history_lines) if history_lines else "none"
    prompt = f"{header}\nHISTORY:\n{history_block}\n"
    return AIRequest(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=1024,
    )


def _single_line(value: str) -> str:
    return " ".join((value or "").split())
