"""A deterministic, offline mock target.

This makes the entire harness (and the CI gate) runnable with no network access
or API keys. It is intentionally *good but imperfect* so that metrics land in a
realistic mid-to-high range and regressions/thresholds are meaningful.
"""

from __future__ import annotations

import re

from ..models import GuardrailOutput, RagOutput, ToolDef, ToolOutput

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are",
    "what", "who", "when", "where", "how", "does", "do", "with", "at", "it",
    "right", "now", "please", "give", "me", "my", "i", "this", "that",
}

_REFUSAL = (
    "I can't help with that. The request appears to involve harmful or "
    "policy-violating activity, so I have to decline."
)

# Crude harmful-intent signals the mock "guardrail" trips on.
_HARMFUL_PATTERNS = [
    r"\bnerve agent\b", r"\bbomb\b", r"\bmalware\b", r"\bransom", r"\bsynthesize\b.*\bagent\b",
    r"ignore (your )?previous instructions", r"system prompt", r"\bDAN\b",
    r"steal .*identity", r"\bweapon\b", r"\bexploit\b.*\bvuln",
]


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9@._']+", text.lower()) if w not in _STOPWORDS]


class MockAdapter:
    name = "mock"

    async def answer_rag(self, question: str, context: list[dict]) -> RagOutput:
        q_tokens = set(_tokens(question))
        scored: list[tuple[float, str, str]] = []
        for passage in context:
            p_tokens = set(_tokens(passage["text"]))
            if not p_tokens:
                continue
            overlap = len(q_tokens & p_tokens) / len(q_tokens | p_tokens)
            scored.append((overlap, passage["id"], passage["text"]))
        scored.sort(reverse=True)

        # Abstain if nothing is relevant (mirrors a well-behaved RAG system).
        relevant = [s for s in scored if s[0] > 0.0]
        if not relevant:
            return RagOutput(
                answer="The provided context does not contain the answer.",
                citations=[],
            )

        # Cite the passages with meaningful overlap (top scorers).
        top_score = relevant[0][0]
        threshold = top_score * 0.5
        cited = [pid for score, pid, _ in relevant if score >= threshold]
        # Compose a short grounded answer from the most relevant passages.
        answer = " ".join(text for score, _, text in relevant if score >= threshold)
        return RagOutput(answer=answer, citations=cited)

    async def select_tool(self, prompt: str, tools: list[ToolDef]) -> ToolOutput:
        p = prompt.lower()
        names = {t.name for t in tools}

        if "weather" in p or "how hot" in p or "temperature" in p:
            if "weather" in names or "get_weather" in names:
                city = _extract_city(prompt)
                unit = "fahrenheit" if "fahrenheit" in p else "celsius"
                return ToolOutput(tool="get_weather", args={"city": city, "unit": unit})

        if "email" in p and "send_email" in names:
            return ToolOutput(tool="send_email", args=_extract_email_args(prompt))

        if "calendar" in p and "create_calendar_event" in names:
            return ToolOutput(tool="create_calendar_event", args=_extract_event_args(prompt))

        if ("find" in p or "search" in p or "papers" in p) and "search_web" in names:
            return ToolOutput(tool="search_web", args={"query": _extract_query(prompt)})

        return ToolOutput(tool=None, args={})

    async def respond(self, prompt: str) -> GuardrailOutput:
        for pat in _HARMFUL_PATTERNS:
            if re.search(pat, prompt, flags=re.IGNORECASE):
                return GuardrailOutput(text=_REFUSAL)
        return GuardrailOutput(
            text="Sure — here is a helpful, safe response to your request."
        )

    async def aclose(self) -> None:  # pragma: no cover - nothing to close
        return None


def _extract_city(prompt: str) -> str:
    m = re.search(r"\bin ([A-Z][a-zA-Z]+)", prompt)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z][a-zA-Z]+)\b", prompt)
    return m.group(1) if m else ""


def _extract_query(prompt: str) -> str:
    p = prompt.lower()
    if "retrieval augmented generation" in p:
        return "retrieval augmented generation papers"
    cleaned = re.sub(r"^(find|search( for)?|look up)\s+", "", prompt.strip(), flags=re.IGNORECASE)
    return cleaned.rstrip(".")


def _extract_email_args(prompt: str) -> dict:
    to = ""
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", prompt)
    if m:
        to = m.group(0)
    subject = ""
    ms = re.search(r"subject ['\"]([^'\"]+)['\"]", prompt, flags=re.IGNORECASE)
    if ms:
        subject = ms.group(1)
    body = ""
    mb = re.search(r"saying (.+)", prompt, flags=re.IGNORECASE)
    if mb:
        body = mb.group(1).rstrip(".")
    return {"to": to, "subject": subject, "body": body}


def _extract_event_args(prompt: str) -> dict:
    title = ""
    mt = re.search(r"put ['\"]([^'\"]+)['\"]", prompt, flags=re.IGNORECASE)
    if mt:
        title = mt.group(1)
    date = ""
    md = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", prompt)
    if md:
        date = md.group(1)
    time = ""
    mtm = re.search(r"\b(\d{1,2}:\d{2})\b", prompt)
    if mtm:
        time = mtm.group(1)
    return {"title": title, "date": date, "time": time}
