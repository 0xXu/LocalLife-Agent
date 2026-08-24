from __future__ import annotations

import json
from typing import Protocol

from litellm import acompletion

from backend.config import Settings
from backend.domain.models import OfflineVerificationResult, SupplyOption
from backend.supply.twin import SupplyTwin


class OutboundCallTransport(Protocol):
    async def call(self, supply_id: str, request: str) -> str: ...


class TwinCallTransport:
    """Provider-call transport for the local world twin."""

    def __init__(self, supply: SupplyTwin) -> None:
        self.supply = supply

    async def call(self, supply_id: str, request: str) -> str:
        option = await self.supply.get(supply_id)
        if option is None:
            return "商户号码未接通，当前无法确认。"
        merchant_note = str(option.metadata.get("merchant_note", option.evidence.detail))
        return f"代办请求：{request}\n商户回复：{merchant_note}"


class AiOutboundCallAdapter:
    """Places a provider call and turns its transcript into lifecycle evidence."""

    def __init__(self, settings: Settings, transport: OutboundCallTransport) -> None:
        self.settings = settings
        self.transport = transport

    async def verify(self, option: SupplyOption, request: str) -> OfflineVerificationResult:
        transcript = await self.transport.call(option.id, request)
        schema = OfflineVerificationResult.model_json_schema()
        response = await acompletion(
            model=self.settings.deepseek_litellm_model,
            api_base=self.settings.deepseek_base_url,
            api_key=self.settings.deepseek_api_key,
            temperature=0,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": self.settings.deepseek_thinking}},
            messages=[{
                "role": "user",
                "content": (
                    "Extract only merchant-confirmed facts from this outbound call. "
                    "Do not infer missing facts. Return JSON matching this schema: "
                    f"{json.dumps(schema, ensure_ascii=False)}\n"
                    f"supply_id={option.id}\n{transcript}"
                ),
            }],
        )
        content = response.choices[0].message.content or "{}"
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        payload = json.loads(cleaned)
        payload["supply_id"] = option.id
        payload.pop("verified_at", None)
        return OfflineVerificationResult.model_validate(payload)
