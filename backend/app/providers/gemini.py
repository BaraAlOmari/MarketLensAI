"""Thin wrapper over the google-genai Interactions API for JSON-schema output.

Verified 2026-10-10 against ai.google.dev/gemini-api/docs/structured-output and the
installed SDK (google-genai 2.29.0): `client.aio.interactions.create(...)` with
`response_format={"type": "text", "mime_type": "application/json", "schema": ...}`
returns an Interaction whose `output_text` holds the JSON and `usage` the token counts.

Retries: the Interactions client retries on its own by default (3 retries, connection
errors included), which nested inside `with_retries` let one bad batch hang for over an
hour on 2026-10-12. The client is created with the minimum the SDK allows (1 internal
retry), and each attempt gets a hard `asyncio.wait_for` deadline so `with_retries` stays
in control of total time.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from app.providers.retry import with_retries


@dataclass(frozen=True)
class JsonResult:
    text: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int


class GeminiJsonClient:
    def __init__(self, api_key: str, model: str, timeout_s: float = 240.0) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self.model = model
        self._timeout_s = timeout_s

    async def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        thinking_level: str = "low",
    ) -> JsonResult:
        async def call():
            request = self._client.aio.interactions.create(
                model=self.model,
                system_instruction=system,
                input=prompt,
                response_format={"type": "text", "mime_type": "application/json", "schema": schema},
                generation_config={"thinking_level": thinking_level},
                store=False,
                timeout=self._timeout_s,
            )
            return await asyncio.wait_for(request, timeout=self._timeout_s + 10)

        interaction = await with_retries(call)
        usage = interaction.usage
        return JsonResult(
            text=interaction.output_text or "",
            input_tokens=(usage.total_input_tokens or 0) if usage else 0,
            output_tokens=(usage.total_output_tokens or 0) if usage else 0,
            thought_tokens=(usage.total_thought_tokens or 0) if usage else 0,
        )
