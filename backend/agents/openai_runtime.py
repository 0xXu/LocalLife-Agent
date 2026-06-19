from __future__ import annotations

import json
import re
from typing import Any

from agents import Agent, Runner, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from backend.agents.guardrails import require_grounded_action
from backend.agents.final_validation_tool import FINAL_VALIDATION_DONE_KEY, FinalValidationTool
from backend.agents.intent_extraction_tool import (
    CLARIFICATION_QUEUE_KEY,
    LLM_MISSING_FIELDS_KEY,
    REQUIRED_FIELD_PRIORITY,
    ConstraintExtractor,
    IntentExtractionTool,
)
from backend.agents.runtime import (
    EventSink,
    ExecuteActionsRequest,
    ExecutionResult,
    PlanRunRequest,
    PlanRunResult,
    RuntimeContext,
)
from backend.llm.config import LLMConfig


class OpenAIAgentsRuntime:
    def __init__(
        self,
        dry_run: bool = False,
        model: str | None = None,
        planner_model: Any | None = None,
        constraint_extractor: ConstraintExtractor | None = None,
        intent_tool: IntentExtractionTool | None = None,
        final_validation_tool: FinalValidationTool | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.model = model
        self.planner = self._build_planner(planner_model or model)
        self.intent_tool = intent_tool or IntentExtractionTool(
            dry_run=dry_run,
            model=planner_model or model,
            constraint_extractor=constraint_extractor,
        )
        self.final_validation_tool = final_validation_tool or FinalValidationTool(
            dry_run=dry_run,
            model=planner_model or model,
        )

    @classmethod
    def from_llm_config(cls, config: LLMConfig) -> "OpenAIAgentsRuntime":
        if not config.remote_enabled or not config.is_configured:
            return cls(dry_run=True, model=config.model)

        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        set_tracing_disabled(True)
        planner_model = OpenAIChatCompletionsModel(model=config.model, openai_client=client)
        return cls(dry_run=False, model=config.model, planner_model=planner_model)

    def _build_planner(self, model: str | Any | None) -> Agent:
        kwargs: dict[str, Any] = {
            "name": "PlannerAgent",
            "instructions": "Create grounded local-life plans. Return only validated product-safe output.",
        }
        if model is not None:
            kwargs["model"] = model
        return Agent(**kwargs)

    async def start_plan(
        self,
        request: PlanRunRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> PlanRunResult:
        await sink("agent.started", {"agent": "planner"})
        constraints = self._merge_known_constraints(request)
        if not self._has_clarification_queue(constraints):
            constraints = await self._extract_constraints(request, sink)
        missing_fields = self._pending_clarification_fields(constraints)
        if missing_fields:
            clarification = self._clarification_for(missing_fields[0], constraints)
            await sink("clarification.required", clarification)
            return PlanRunResult(
                status="needs_clarification",
                clarification=clarification,
                validation={"valid": False, "missing_fields": missing_fields},
            )

        if not constraints.get(FINAL_VALIDATION_DONE_KEY):
            validation_result = await self.final_validation_tool.validate(
                request,
                constraints=constraints,
                sink=sink,
            )
            constraints = dict(validation_result.get("constraints", constraints))
            missing_fields = [
                str(field)
                for field in validation_result.get("missing_fields", [])
                if str(field) in self._required_field_priority() and not constraints.get(str(field))
            ]
            if missing_fields:
                constraints[CLARIFICATION_QUEUE_KEY] = missing_fields
                clarification = self._clarification_for(missing_fields[0], constraints)
                await sink("clarification.required", clarification)
                return PlanRunResult(
                    status="needs_clarification",
                    clarification=clarification,
                    validation={"valid": False, "missing_fields": missing_fields},
                )
            constraints[FINAL_VALIDATION_DONE_KEY] = True

        if self.dry_run:
            return await self._approval_plan_result(
                request=request,
                context=context,
                sink=sink,
                summary=request.goal,
                constraints=constraints,
            )

        run_result = await Runner.run(self.planner, self._planner_prompt(request, constraints))
        final_output = getattr(run_result, "final_output", run_result)
        planner_plan = self._parse_planner_plan(final_output)
        self._require_valid_planner_plan(planner_plan)
        return await self._approval_plan_result(
            request=request,
            context=context,
            sink=sink,
            planner_output=planner_plan,
            constraints=constraints,
            raw_output=run_result,
        )

    async def _approval_plan_result(
        self,
        *,
        request: PlanRunRequest,
        context: RuntimeContext,
        sink: EventSink,
        summary: str | None = None,
        planner_output: Any | None = None,
        constraints: dict[str, Any],
        raw_output: Any | None = None,
    ) -> PlanRunResult:
        pending_action = {
            "action_id": "act_send_plan_summary",
            "id": "act_send_plan_summary",
            "type": "send_plan_message",
            "tool": "messaging",
            "target": context.user_id,
            "label": "发送计划摘要",
            "detail": "把确认后的出行方案发送给用户",
            "status": "pending",
            "payload": {"plan_id": context.plan_id},
        }
        require_grounded_action(pending_action)
        planner_plan = self._parse_planner_plan(planner_output if planner_output is not None else summary)
        plan = {
            "id": context.plan_id,
            "status": "approval_required",
            "title": "本地生活计划",
            "summary": self._short_summary(
                summary or (planner_output if isinstance(planner_output, str) else "") or request.goal
            ),
            "constraint_fit": {
                "distance": 0.82,
                "time": 0.82,
                "budget": 0.7,
            },
            "overview": {
                "theme": "轻量出行",
                "totalDuration": "约 2-3 小时",
                "driveTime": "待确认",
                "walkingDistance": "待确认",
                "estimatedCost": "按实际选择",
                "score": 82,
            },
            "itinerary": [],
            "actions": [pending_action],
            "receipts": [],
            "badges": (self._constraint_match_labels(constraints) or ["待确认"])[:4],
        }
        plan = self._merge_planner_plan(plan, planner_plan)
        plan["id"] = context.plan_id
        plan["status"] = "approval_required"
        plan["actions"] = [pending_action]
        await sink("approval.required", {"plan_id": context.plan_id, "actions": [pending_action]})
        return PlanRunResult(
            status="approval_required",
            plan=plan,
            validation={"valid": True},
            pending_actions=[pending_action],
            raw_output=raw_output,
        )

    def _planner_prompt(self, request: PlanRunRequest, constraints: dict[str, Any]) -> str:
        visible_constraints = self._visible_constraints(constraints)
        return (
            "Create a concise, concrete local-life plan from the confirmed user constraints.\n"
            "Do not ask for information that is already present in the constraints.\n\n"
            f"Original goal:\n{request.goal}\n\n"
            "Confirmed constraints JSON:\n"
            f"{json.dumps(visible_constraints, ensure_ascii=False)}\n\n"
            "User clarification answers JSON:\n"
            f"{json.dumps(request.answers, ensure_ascii=False)}\n\n"
            "Return only valid compact JSON. Do not return Markdown. Required shape:\n"
            "{"
            "\"title\":\"短标题\","
            "\"summary\":\"不超过80字的短摘要\","
            "\"overview\":{\"theme\":\"\",\"totalDuration\":\"\",\"driveTime\":\"\",\"walkingDistance\":\"\",\"estimatedCost\":\"\",\"score\":0},"
            "\"constraint_fit\":{\"distance\":0.0,\"time\":0.0,\"budget\":0.0},"
            "\"variants\":[{\"id\":\"variant_main\",\"kind\":\"main\",\"title\":\"\",\"summary\":\"\",\"score\":0,\"estimated_budget\":0,"
            "\"itinerary\":[{\"start\":\"\",\"end\":\"\",\"type\":\"activity\",\"title\":\"\",\"reason\":\"\",\"cost\":\"\"}]}],"
            "\"itinerary\":[{\"start\":\"\",\"end\":\"\",\"type\":\"activity\",\"title\":\"\",\"reason\":\"\",\"cost\":\"\"}],"
            "\"badges\":[\"标签\"]"
            "}. itinerary and variants must be non-empty."
        )

    def _parse_planner_plan(self, output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            return dict(output)
        if not isinstance(output, str):
            return {}
        text = output.strip()
        if not text:
            return {}
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        nested_plan = parsed.get("plan")
        return nested_plan if isinstance(nested_plan, dict) else parsed

    def _merge_planner_plan(self, base: dict[str, Any], planner_plan: dict[str, Any]) -> dict[str, Any]:
        if not planner_plan:
            return base
        merged = dict(base)
        if isinstance(planner_plan.get("title"), str) and planner_plan["title"].strip():
            merged["title"] = self._plain_text(planner_plan["title"], limit=48)
        if isinstance(planner_plan.get("summary"), str) and planner_plan["summary"].strip():
            merged["summary"] = self._short_summary(planner_plan["summary"])
        if isinstance(planner_plan.get("overview"), dict):
            merged["overview"] = self._merge_overview(merged["overview"], planner_plan["overview"])
        if isinstance(planner_plan.get("constraint_fit"), dict):
            merged["constraint_fit"] = self._merge_constraint_fit(merged["constraint_fit"], planner_plan["constraint_fit"])
        if isinstance(planner_plan.get("itinerary"), list):
            merged["itinerary"] = planner_plan["itinerary"]
        if isinstance(planner_plan.get("variants"), list):
            merged["variants"] = self._normalize_variants(planner_plan["variants"])
        if isinstance(planner_plan.get("badges"), list):
            badges = [self._plain_text(str(badge), limit=16) for badge in planner_plan["badges"] if str(badge).strip()]
            if badges:
                merged["badges"] = badges[:4]
        return merged

    def _require_valid_planner_plan(self, planner_plan: dict[str, Any]) -> None:
        required_string_fields = ("title", "summary")
        if not planner_plan or any(not str(planner_plan.get(field) or "").strip() for field in required_string_fields):
            raise RuntimeError("planner_contract_invalid:missing_title_or_summary")
        if not isinstance(planner_plan.get("overview"), dict):
            raise RuntimeError("planner_contract_invalid:missing_overview")
        if not isinstance(planner_plan.get("constraint_fit"), dict):
            raise RuntimeError("planner_contract_invalid:missing_constraint_fit")
        itinerary = planner_plan.get("itinerary")
        if not self._has_renderable_itinerary(itinerary):
            raise RuntimeError("planner_contract_invalid:missing_itinerary")
        variants = planner_plan.get("variants")
        if not isinstance(variants, list) or not variants:
            raise RuntimeError("planner_contract_invalid:missing_variants")
        if not any(
            isinstance(variant, dict)
            and str(variant.get("title") or "").strip()
            and self._has_renderable_itinerary(variant.get("itinerary"))
            for variant in variants
        ):
            raise RuntimeError("planner_contract_invalid:missing_variant_itinerary")

    def _has_renderable_itinerary(self, value: Any) -> bool:
        return isinstance(value, list) and any(
            isinstance(step, dict) and str(step.get("title") or "").strip() for step in value
        )

    def _merge_overview(self, base: dict[str, Any], overview: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key in ("theme", "totalDuration", "driveTime", "walkingDistance", "estimatedCost"):
            value = overview.get(key)
            if isinstance(value, str) and value.strip():
                merged[key] = self._plain_text(value, limit=48)
        score = overview.get("score")
        if isinstance(score, (int, float)):
            merged["score"] = max(0, min(100, round(score)))
        return merged

    def _merge_constraint_fit(self, base: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in fit.items():
            if isinstance(value, (int, float)) and 0 <= value <= 1:
                merged[str(key)] = float(value)
        return merged

    def _normalize_variants(self, variants: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, variant in enumerate(variants):
            if not isinstance(variant, dict):
                continue
            title = variant.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            item = {
                "id": str(variant.get("id") or f"variant_{index + 1}"),
                "kind": str(variant.get("kind") or "main"),
                "title": self._plain_text(title, limit=48),
                "summary": self._short_summary(str(variant.get("summary") or title)),
                "itinerary": variant.get("itinerary") if isinstance(variant.get("itinerary"), list) else [],
                "actions": [],
            }
            score = variant.get("score")
            if isinstance(score, (int, float)):
                item["score"] = max(0, min(100, round(score)))
            estimated_budget = variant.get("estimated_budget")
            if isinstance(estimated_budget, (int, float)):
                item["estimated_budget"] = round(estimated_budget)
            if isinstance(variant.get("constraint_fit"), dict):
                item["constraint_fit"] = self._merge_constraint_fit({}, variant["constraint_fit"])
            if isinstance(variant.get("overview"), dict):
                item["overview"] = self._merge_overview(
                    {
                        "theme": item["title"],
                        "totalDuration": "待确认",
                        "driveTime": "待确认",
                        "walkingDistance": "待确认",
                        "estimatedCost": "按实际选择",
                        "score": item.get("score", 82),
                    },
                    variant["overview"],
                )
            normalized.append(item)
        return normalized

    def _short_summary(self, value: str, limit: int = 120) -> str:
        return self._plain_text(value, limit=limit)

    def _plain_text(self, value: str, limit: int = 120) -> str:
        text = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_`>|]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    async def _extract_constraints(self, request: PlanRunRequest, sink: EventSink) -> dict[str, Any]:
        return await self.intent_tool.extract(
            request,
            base_constraints=self._merge_known_constraints(request),
            sink=sink,
        )

    def _missing_required_fields(self, constraints: dict[str, Any]) -> list[str]:
        llm_missing = constraints.get(LLM_MISSING_FIELDS_KEY)
        if isinstance(llm_missing, list) and llm_missing:
            priority = [str(field) for field in llm_missing if str(field) in self._required_field_priority()]
        else:
            priority = self._required_field_priority()
        return [field for field in priority if not constraints.get(field)]

    def _required_field_priority(self) -> list[str]:
        return REQUIRED_FIELD_PRIORITY

    def _merge_known_constraints(self, request: PlanRunRequest) -> dict[str, Any]:
        constraints = dict(request.constraints)
        constraints.update({key: value for key, value in request.answers.items() if value not in (None, "")})
        return constraints

    def _has_clarification_queue(self, constraints: dict[str, Any]) -> bool:
        queue = constraints.get(CLARIFICATION_QUEUE_KEY)
        return isinstance(queue, list)

    def _pending_clarification_fields(self, constraints: dict[str, Any]) -> list[str]:
        queue = constraints.get(CLARIFICATION_QUEUE_KEY)
        if isinstance(queue, list):
            pending = [
                str(field)
                for field in queue
                if str(field) in self._required_field_priority() and not constraints.get(str(field))
            ]
        else:
            pending = self._missing_required_fields(constraints)
        if pending:
            constraints[CLARIFICATION_QUEUE_KEY] = pending
        else:
            constraints.pop(CLARIFICATION_QUEUE_KEY, None)
        return pending

    def _clarification_for(self, field: str, constraints: dict[str, Any]) -> dict[str, Any]:
        if field == "time_window":
            return {
                "question": {
                    "id": "time_window",
                    "label": "今天大概几点开始？",
                    "description": "时间范围会影响营业状态、路线顺序和预约动作。",
                    "kind": "time",
                    "required": True,
                    "options": [
                        {"label": "今天下午 2 点", "value": "今天下午 2 点"},
                        {"label": "今天下午 4 点", "value": "今天下午 4 点"},
                        {"label": "今晚 7 点", "value": "今晚 7 点"},
                    ],
                    "allow_custom": True,
                },
                "partial_constraints": self._partial_constraints(constraints),
                "missing_fields": [field],
            }
        if field == "start_location":
            return {
                "question": {
                    "id": "start_location",
                    "label": "你想从哪里出发？",
                    "description": "出发点会影响距离、路线顺序和可选区域。",
                    "kind": "location",
                    "required": True,
                    "options": [
                        {"label": "家附近", "value": "家附近"},
                        {"label": "公司附近", "value": "公司附近"},
                        {"label": "当前定位附近", "value": "当前定位附近"},
                    ],
                    "allow_custom": True,
                },
                "partial_constraints": self._partial_constraints(constraints),
                "missing_fields": [field],
            }
        if field == "party_size":
            return {
                "question": {
                    "id": "party_size",
                    "label": "这次一共有几位？",
                    "description": "人数会影响餐厅容量、活动空间和预算估算。",
                    "kind": "number",
                    "required": True,
                    "options": [
                        {"label": "1 位", "value": 1},
                        {"label": "2 位", "value": 2},
                        {"label": "3-4 位", "value": 4},
                    ],
                    "allow_custom": True,
                    "validation": {"min": 1, "max": 20},
                },
                "partial_constraints": self._partial_constraints(constraints),
                "missing_fields": [field],
            }
        if field == "activity_preference":
            return {
                "question": {
                    "id": "activity_preference",
                    "label": "你更想要哪种体验？",
                    "description": "体验偏好会决定候选类型，而不是只给泛泛的地点。",
                    "kind": "single_select",
                    "required": True,
                    "options": [
                        {"label": "散步逛逛", "value": "散步逛逛"},
                        {"label": "吃饭喝咖啡", "value": "吃饭喝咖啡"},
                        {"label": "室内放松", "value": "室内放松"},
                        {"label": "拍照打卡", "value": "拍照打卡"},
                    ],
                    "allow_custom": True,
                },
                "partial_constraints": self._partial_constraints(constraints),
                "missing_fields": [field],
            }
        raise RuntimeError(f"unsupported_clarification_field:{field}")

    def _partial_constraints(self, constraints: dict[str, Any]) -> dict[str, Any]:
        partial = dict(constraints)
        partial.pop(LLM_MISSING_FIELDS_KEY, None)
        return partial

    def _visible_constraints(self, constraints: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in constraints.items()
            if not key.startswith("__")
        }

    def _constraint_match_labels(self, constraints: dict[str, Any]) -> list[str]:
        labels = {
            "time_window": "已确认出发时间",
            "start_location": "已确认出发位置",
            "party_size": "已确认同行人数",
            "activity_preference": "已确认体验偏好",
        }
        return [label for field, label in labels.items() if constraints.get(field)]

    async def execute_actions(
        self,
        request: ExecuteActionsRequest,
        context: RuntimeContext,
        sink: EventSink,
    ) -> ExecutionResult:
        await sink("actions.execution.started", {"plan_id": context.plan_id, "action_ids": request.action_ids})
        receipts = [
            {
                "id": f"receipt_{index + 1}",
                "action_id": action_id,
                "plan_id": context.plan_id,
                "status": "confirmed",
                "run_id": context.run_id,
            }
            for index, action_id in enumerate(request.action_ids)
        ]
        await sink("actions.execution.completed", {"plan_id": context.plan_id, "receipts": receipts})
        return ExecutionResult(status="completed", receipts=receipts)
