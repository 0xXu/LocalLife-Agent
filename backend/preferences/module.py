from __future__ import annotations

from backend.domain.models import (
    PreferenceEvidence,
    PreferenceFact,
    PreferenceFactEdit,
    utc_now,
)
from backend.storage import DocumentStore


class PreferenceModule:
    """Turns task evidence into revisable, contextual user facts."""

    namespace = "preference_facts"
    source_authority = {
        "fulfillment_outcome": 1,
        "actual_choice": 2,
        "cancellation": 2,
        "explicit_expression": 3,
        "agent_override": 4,
    }

    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    async def ingest(
        self,
        user_id: str,
        evidence: list[PreferenceEvidence],
    ) -> list[PreferenceFact]:
        changed: list[PreferenceFact] = []
        for item in evidence:
            facts = await self.list(user_id, include_inactive=True)
            predecessor = next(
                (
                    fact
                    for fact in reversed(facts)
                    if fact.active
                    and fact.subject == item.subject
                    and fact.context_scope == item.context_scope
                    and fact.dimension == item.dimension
                ),
                None,
            )
            if predecessor and (
                predecessor.preference == item.preference
                and predecessor.polarity == item.polarity
            ):
                predecessor.confidence = max(predecessor.confidence, item.confidence)
                predecessor.observed_at = item.observed_at
                if self.source_authority[item.source] >= self.source_authority[predecessor.source]:
                    predecessor.source = item.source
                predecessor.task_id = item.task_id
                await self.store.save(
                    self.namespace,
                    predecessor.id,
                    predecessor.model_dump(mode="json"),
                )
                changed.append(predecessor)
                continue

            if (
                predecessor
                and self.source_authority[item.source] < self.source_authority[predecessor.source]
            ):
                continue

            if predecessor:
                predecessor.active = False
                await self.store.save(
                    self.namespace,
                    predecessor.id,
                    predecessor.model_dump(mode="json"),
                )
            fact = PreferenceFact(
                user_id=user_id,
                subject=item.subject,
                context_scope=item.context_scope,
                dimension=item.dimension,
                preference=item.preference,
                polarity=item.polarity,
                source=item.source,
                confidence=item.confidence,
                observed_at=item.observed_at,
                valid_from=utc_now(),
                supersedes=predecessor.id if predecessor else None,
                task_id=item.task_id,
            )
            await self.store.save(
                self.namespace,
                fact.id,
                fact.model_dump(mode="json"),
            )
            changed.append(fact)
        return changed

    async def relevant(
        self,
        user_id: str,
        *,
        context_scope: str,
        query: str,
        limit: int = 12,
    ) -> list[PreferenceFact]:
        facts = await self.list(user_id)
        terms = {
            token.lower()
            for token in query.replace("，", " ").replace("。", " ").split()
            if len(token) > 1
        }

        def relevance(fact: PreferenceFact) -> tuple[int, float, object]:
            scope_fit = 2 if fact.context_scope == context_scope else 1 if fact.context_scope == "general" else 0
            text = f"{fact.dimension} {fact.preference}".lower()
            semantic_fit = sum(term in text for term in terms)
            return scope_fit + semantic_fit, fact.confidence, fact.observed_at

        ranked = [fact for fact in facts if relevance(fact)[0] > 0]
        ranked.sort(key=relevance, reverse=True)
        return ranked[:limit]

    async def list(
        self,
        user_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[PreferenceFact]:
        facts = [
            PreferenceFact.model_validate(item)
            for item in await self.store.scan(self.namespace)
            if item.get("user_id") == user_id
            and (include_inactive or item.get("active", True))
        ]
        return sorted(facts, key=lambda item: item.observed_at)

    async def revise(
        self,
        user_id: str,
        fact_id: str,
        edit: PreferenceFactEdit,
    ) -> PreferenceFact:
        payload = await self.store.load(self.namespace, fact_id)
        if payload is None or payload.get("user_id") != user_id:
            raise ValueError("preference fact does not exist")
        fact = PreferenceFact.model_validate(payload)
        if edit.delete:
            fact.active = False
        else:
            for field in ("context_scope", "preference", "polarity", "confidence"):
                value = getattr(edit, field)
                if value is not None:
                    setattr(fact, field, value)
            fact.source = "agent_override"
            fact.observed_at = utc_now()
        await self.store.save(self.namespace, fact.id, fact.model_dump(mode="json"))
        return fact
