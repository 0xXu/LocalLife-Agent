from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from backend.actions.ledger import ActionLedger, ledger_from_actions
from backend.data.catalog import LocalDataCatalog
from backend.llm import LLMConfig
from backend.models.schemas import PlanState, action_dict, state_response, to_dict, variant_dict
from backend.orchestrator import PlanningPipeline
from backend.profile.models import UserPreference, UserProfile
from backend.profile.store import UserProfileStore
from backend.revision.diff import build_plan_diff
from backend.revision.parser import feedback_to_delta
from backend.storage.repository import PlanRepository
from backend.tools import LocalToolRegistry, TraceStore


class PlanningService:
    def __init__(
        self,
        catalog: LocalDataCatalog | None = None,
        llm_config: LLMConfig | None = None,
        repository_path: Path | str | None = None,
        profile_store_path: Path | str | None = None,
    ) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.tool_registry = LocalToolRegistry(self.catalog)
        self.trace_store = TraceStore()
        self.repository = PlanRepository(repository_path) if repository_path else None
        self.profile_store = UserProfileStore(profile_store_path or Path(".weekendpilot/profiles.sqlite"))
        self._plans: dict[str, PlanState] = {}
        self._checkpoints: dict[str, dict] = {}
        self._ledgers: dict[str, ActionLedger] = {}
        if self.repository:
            for state in self.repository.list_states():
                self._plans[state.plan_id] = state
                self._checkpoints[state.plan_id] = to_dict(state.checkpoint())
                self.trace_store.save(state.plan_id, state.trace)

    def build_plan(self, goal: str, on_progress: Callable[[str, str], None] | None = None, on_token: Callable[[str], None] | None = None, user_id: str = "local_demo_user") -> dict:
        if not goal.strip():
            raise ValueError("validation_error")
        profile = self.profile_store.get(user_id) if self.profile_store else None
        state = self.pipeline.build(goal, on_progress=on_progress, on_token=on_token, profile=profile)
        self._save(state)
        response = state_response(state)
        if profile:
            response["user_profile"] = profile.as_dict()
        return response

    def get_plan(self, plan_id: str) -> dict:
        state = self._require_plan(plan_id)
        response = state_response(state)
        response["checkpoint"] = self._checkpoints[plan_id]
        return response

    def list_plans(self) -> dict:
        plans = [self._summary(state) for state in reversed(list(self._plans.values()))]
        return {"plans": plans, "total": len(plans)}

    def patch_constraints(self, plan_id: str, updates: dict) -> dict:
        state = self._require_plan(plan_id)
        rebuilt = self.pipeline.build(state.goal, updates)
        rebuilt.plan_id = plan_id
        self._save(rebuilt)
        return state_response(rebuilt)

    def build_alternatives(self, plan_id: str) -> dict:
        state = self._require_plan(plan_id)
        return {"plan_id": plan_id, "alternatives": [variant_dict(variant) for variant in state.variants]}

    def confirm_plan(self, plan_id: str, confirmed: bool) -> dict:
        if not confirmed:
            raise PermissionError("confirmation_required")
        state = self._require_plan(plan_id)
        state.status = "confirmed"
        self._ensure_ledger(state)
        self._save(state)
        response = state_response(state)
        response["pending_actions"] = [action_dict(action) for action in state.pending_actions]
        return response

    def execute_plan(self, plan_id: str, confirmed: bool, selected_action_ids: list[str] | None = None, idempotency_key: str = "") -> dict:
        if not confirmed:
            raise PermissionError("confirmation_required")
        state = self._require_plan(plan_id)
        if state.status not in {"confirmed", "pending_confirmation", "recovered_pending_confirmation", "completed"}:
            raise ValueError("validation_error")
        ledger = self._ensure_ledger(state)
        all_action_ids = [entry.action_id for entry in ledger.entries]
        selected = selected_action_ids if selected_action_ids is not None else all_action_ids
        if not idempotency_key:
            idempotency_key = f"{plan_id}:{','.join(selected or ['none'])}"
        entries = ledger.mark_executing(selected, idempotency_key)
        if not entries:
            self._save(state)
            return state_response(state)
        state.pending_actions = [entry.action for entry in entries]
        state = self.pipeline.execute(state)
        for receipt in state.receipts:
            for entry in entries:
                if entry.action.tool == receipt.tool:
                    ledger.mark_succeeded(entry.action_id, receipt.id)
                    break
        self._sync_ledger_state(state, ledger)
        self._save(state)
        return state_response(state)

    def recover_plan(self, plan_id: str, reason: str) -> dict:
        state = self._require_plan(plan_id)
        state = self.pipeline.recover(state, reason)
        self._save(state)
        return state_response(state)

    def revise_plan(self, plan_id: str, body: dict) -> dict:
        state = self._require_plan(plan_id)
        before = state.plan_dict()
        delta = feedback_to_delta(body)
        profile = self.profile_store.get(delta.user_id) if self.profile_store else None
        revised = self.pipeline.revise(state, delta, profile=profile)
        after = revised.plan_dict()
        diff = build_plan_diff(before, after, changed_constraints_for_revision(state, delta.constraint_updates))
        learned = []
        if delta.save_to_profile and self.profile_store:
            profile = self.profile_store.get(delta.user_id)
            for key, value in delta.constraint_updates.items():
                pref = UserPreference(key, value, "feedback", 0.72, "long_term", delta.feedback_text)
                profile.learned_preferences.append(pref)
                learned.append(pref.as_dict())
            self.profile_store.save(profile)
        self._save(revised)
        response = state_response(revised)
        response["revision"] = {
            "revision_id": delta.revision_id,
            "feedback_text": delta.feedback_text,
            "constraint_updates": delta.constraint_updates,
        }
        response["diff"] = diff
        response["learned_preferences"] = learned
        return response

    def get_trace(self, plan_id: str) -> list[dict]:
        self._require_plan(plan_id)
        return self.trace_store.get(plan_id)

    def list_revisions(self, plan_id: str) -> dict:
        state = self._require_plan(plan_id)
        revision = state.context.get("revision", {})
        return {"plan_id": plan_id, "revisions": [revision] if revision else []}

    def tool_schemas(self) -> dict:
        return {"tools": self.tool_registry.schemas()}

    def get_user_profile(self, user_id: str) -> dict:
        return self.profile_store.get(user_id).as_dict()

    def save_user_profile(self, profile: UserProfile) -> dict:
        self.profile_store.save(profile)
        return profile.as_dict()

    def _save(self, state: PlanState) -> None:
        self._plans[state.plan_id] = state
        self.trace_store.save(state.plan_id, state.trace)
        self._checkpoints[state.plan_id] = to_dict(state.checkpoint())
        if self.repository:
            self.repository.save_state(state.plan_id, state)

    def _require_plan(self, plan_id: str) -> PlanState:
        if plan_id not in self._plans:
            raise KeyError("plan_not_found")
        return self._plans[plan_id]

    def _summary(self, state: PlanState) -> dict:
        plan = state.plan_dict()
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        status = "completed" if state.status == "completed" else "executing" if state.status == "executing" else "saved"
        constraints = state.constraints
        tags = []
        if constraints:
            tags.append({"family": "家庭", "friends": "朋友", "date": "约会", "rainy_indoor": "雨天"}.get(constraints.scenario, "本地"))
            tags.extend(str(tag) for tag in constraints.preferences.get("activity", [])[:2])
        return {
            "id": state.plan_id,
            "title": plan["title"],
            "status": status,
            "summary": plan["summary"],
            "created_at": now,
            "updated_at": now,
            "tags": tags or ["本地生活"],
            "location": f"{constraints.constraints.get('radius_km', 5):g} 公里内" if constraints else "本地",
            "estimated_cost": plan.get("overview", {}).get("estimatedCost"),
            "itinerary_count": len(state.itinerary),
        }

    def _ensure_ledger(self, state: PlanState) -> ActionLedger:
        ledger = self._ledgers.get(state.plan_id)
        if ledger is None:
            ledger = ledger_from_actions(state.plan_id, state.pending_actions)
            self._ledgers[state.plan_id] = ledger
        self._sync_ledger_state(state, ledger)
        return ledger

    def _sync_ledger_state(self, state: PlanState, ledger: ActionLedger) -> None:
        state.action_ledger = {
            "entries": [
                {
                    "action_id": entry.action_id,
                    "status": entry.status,
                    "tool": entry.action.tool,
                    "target": entry.action.target,
                    "receipt_id": entry.receipt_id,
                    "error": entry.error,
                }
                for entry in ledger.entries
            ]
        }


def changed_constraints_for_revision(state: PlanState, updates: dict) -> dict:
    constraints = state.constraints
    changed = {}
    for key, value in updates.items():
        if key not in {"pace", "budget_level", "meal_required", "duration_hours"}:
            continue
        if key == "duration_hours":
            before = constraints.time_window.get("duration_hours", "medium") if constraints else "medium"
        else:
            before = constraints.preferences.get(key, "medium") if constraints else "medium"
        changed[key] = [before, value]
    return changed
