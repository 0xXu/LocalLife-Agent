from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.actions.durable_ledger import DurableActionLedger
from backend.actions.policy import build_executable_actions
from backend.data.catalog import LocalDataCatalog
from backend.graph.state import (
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_VALIDATION_FAILED,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
)
from backend.llm import LLMConfig
from backend.models.schemas import to_dict
from backend.orchestrator import PlanningPipeline
from backend.storage.workflow_repository import WorkflowRepository
from backend.validation.business import validate_revision_for_approval


class WorkflowService:
    def __init__(
        self,
        catalog: LocalDataCatalog | None = None,
        llm_config: LLMConfig | None = None,
        repository_path: Path | str | None = None,
    ) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.repository = WorkflowRepository(repository_path or Path(".weekendpilot/workflow.sqlite"))
        self.ledger = DurableActionLedger(self.repository)

    def start_run(self, goal: str, user_id: str = "local_demo_user") -> dict[str, str]:
        if not goal.strip():
            raise ValueError("validation_error")

        run_id = new_run_id()
        thread_id = new_thread_id()
        plan_id = new_plan_id()
        revision_id = new_revision_id()

        self.repository.create_thread(thread_id, run_id, plan_id, user_id, PHASE_PLANNING)
        state = self.pipeline.build(goal)
        state.plan_id = plan_id

        if state.status == PHASE_NEEDS_CLARIFICATION:
            phase = PHASE_NEEDS_CLARIFICATION
            constraints = to_dict(state.constraints) if state.constraints else {}
            missing_fields = list(state.context.get("missing_fields", []))
            plan_payload = {
                "id": plan_id,
                "status": PHASE_NEEDS_CLARIFICATION,
                "missing_fields": missing_fields,
                "clarifying_questions": list(state.context.get("clarifying_questions", [])),
            }
            validation = {
                "valid": False,
                "blocking": [{"code": PHASE_NEEDS_CLARIFICATION, "missing_fields": missing_fields}],
                "warnings": [],
            }
            actions: list[dict[str, Any]] = []
        else:
            plan_payload = state.plan_dict()
            plan_payload["id"] = plan_id
            if state.route:
                plan_payload["route"] = state.route
            self._ensure_origin_route_leg(plan_payload)

            constraints = dict(plan_payload.get("constraints") or {})
            constraints["user_id"] = user_id

            candidate_lookup = self._candidate_lookup(state.ranked)
            actions = build_executable_actions(revision_id, plan_payload, candidate_lookup, constraints)
            validation = validate_revision_for_approval(
                plan_payload,
                candidate_lookup,
                constraints,
                actions,
                state.context.get("weather", {}),
            )
            phase = PHASE_PENDING_APPROVAL if validation["valid"] else PHASE_VALIDATION_FAILED

        self.repository.save_revision(
            revision_id,
            plan_id,
            1,
            phase,
            goal,
            constraints,
            plan_payload,
            validation,
        )
        if actions:
            self.ledger.seed_actions(revision_id, actions)
        self.repository.update_thread_status(thread_id, phase)

        return {"run_id": run_id, "thread_id": thread_id, "plan_id": plan_id}

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        revision = self.repository.get_latest_revision(plan_id)
        if revision is None:
            raise KeyError("plan_not_found")
        revision_id = revision["revision_id"]
        return {
            "plan_id": plan_id,
            "revision": revision,
            "actions": self.ledger.list_actions(revision_id),
            "receipts": self.ledger.list_receipts(revision_id),
        }

    def list_plans(self) -> dict[str, Any]:
        revisions = [
            revision
            for revision in self.repository.list_latest_revisions()
            if revision["phase"] != PHASE_NEEDS_CLARIFICATION
        ]
        return {"plans": revisions, "total": len(revisions)}

    def _candidate_lookup(self, ranked: Mapping[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for candidates in ranked.values():
            for candidate in candidates:
                enriched = dict(candidate)
                if enriched.get("category") == "restaurant":
                    coupons = self.catalog.coupons_for(str(enriched["id"]))
                    menu = self.catalog.menu_for(str(enriched["id"]))
                    enriched["coupons"] = coupons
                    enriched["menu"] = menu
                    if coupons:
                        enriched["coupon"] = coupons[0]
                for key in ("id", "place_id", "shop_id"):
                    value = enriched.get(key)
                    if value:
                        lookup[str(value)] = enriched
        return lookup

    def _ensure_origin_route_leg(self, plan: dict[str, Any]) -> None:
        itinerary = [step for step in plan.get("itinerary", []) if step.get("type") != "transport"]
        if not itinerary:
            return
        first_place_id = itinerary[0].get("place_id")
        if not first_place_id:
            return
        route = plan.setdefault("route", {})
        legs = route.setdefault("legs", [])
        if any(leg.get("from") == "origin_home" and leg.get("to") == first_place_id for leg in legs):
            return
        legs.insert(
            0,
            {
                "from": "origin_home",
                "to": first_place_id,
                "mode": "taxi",
                "duration_minutes": 12,
                "distance_km": 2.0,
                "route_summary": "本地 seed 路线矩阵估算",
            },
        )
