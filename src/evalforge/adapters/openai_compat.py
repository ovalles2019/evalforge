"""Target adapter for any OpenAI-compatible /chat/completions endpoint.

Works with OpenAI, Azure OpenAI (compatible gateways), vLLM, Ollama's OpenAI
shim, LiteLLM, Together, Groq, etc. It uses native tool-calling when the
endpoint supports it and falls back to JSON-structured prompting otherwise.
"""

from __future__ import annotations

import json

import httpx

from ..models import GuardrailOutput, RagOutput, ToolDef, ToolOutput


class OpenAICompatAdapter:
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    async def _chat(self, messages: list[dict], **kwargs) -> dict:
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json={"model": self.model, "messages": messages, "temperature": 0, **kwargs},
        )
        resp.raise_for_status()
        return resp.json()

    async def answer_rag(self, question: str, context: list[dict]) -> RagOutput:
        ctx = "\n".join(f"[{p['id']}] {p['text']}" for p in context)
        system = (
            "You answer strictly using the provided context. If the answer is not "
            "in the context, say so. Respond as compact JSON: "
            '{"answer": "...", "citations": ["<passage id>", ...]}.'
        )
        user = f"Context:\n{ctx}\n\nQuestion: {question}"
        data = await self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        content = data["choices"][0]["message"]["content"]
        parsed = _safe_json(content)
        return RagOutput(
            answer=str(parsed.get("answer", content)),
            citations=[str(c) for c in parsed.get("citations", [])],
        )

    async def select_tool(self, prompt: str, tools: list[ToolDef]) -> ToolOutput:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": "string", "description": str(v)}
                            for k, v in t.parameters.items()
                        },
                    },
                },
            }
            for t in tools
        ]
        try:
            data = await self._chat(
                [{"role": "user", "content": prompt}],
                tools=oai_tools,
                tool_choice="auto",
            )
            msg = data["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            if calls:
                fn = calls[0]["function"]
                return ToolOutput(tool=fn["name"], args=_safe_json(fn.get("arguments", "{}")))
            return ToolOutput(tool=None, args={})
        except httpx.HTTPStatusError:
            # Endpoint may not support native tool-calling; fall back to JSON prompt.
            return await self._select_tool_json(prompt, tools)

    async def _select_tool_json(self, prompt: str, tools: list[ToolDef]) -> ToolOutput:
        spec = json.dumps([t.model_dump() for t in tools])
        system = (
            "Choose exactly one tool to satisfy the user. Respond as compact JSON: "
            '{"tool": "<name|null>", "args": {...}}. Available tools: ' + spec
        )
        data = await self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = _safe_json(data["choices"][0]["message"]["content"])
        return ToolOutput(tool=parsed.get("tool"), args=parsed.get("args", {}) or {})

    async def respond(self, prompt: str) -> GuardrailOutput:
        data = await self._chat([{"role": "user", "content": prompt}])
        return GuardrailOutput(text=data["choices"][0]["message"].get("content", ""))

    async def aclose(self) -> None:
        await self._client.aclose()


def _safe_json(text: str) -> dict:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
