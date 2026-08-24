from __future__ import annotations

import pytest

from backend.domain.models import (
    Constraint,
    ConstraintKind,
    ExecutionMandate,
    GoalContract,
    PlanGraph,
    PlanNode,
    PlanPolicy,
    ValueSource,
)
from backend.planning import PlanningModule
from backend.storage import InMemoryDocumentStore
from backend.supply import SupplyTwin


@pytest.fixture
async def world() -> SupplyTwin:
    store = InMemoryDocumentStore()
    await store.initialize()
    twin = SupplyTwin(store)
    await twin.initialize()
    return twin


@pytest.fixture
async def planning(world: SupplyTwin) -> PlanningModule:
    return PlanningModule(world)


async def make_plan(world: SupplyTwin) -> PlanGraph:
    specs = [
        ("dinner", "food_yanlan", "18:40", "20:00", []),
        ("show", "activity_comedy", "20:30", "22:00", ["dinner"]),
        ("home", "mobility_home", "22:10", "22:42", ["show"]),
    ]
    nodes: list[PlanNode] = []
    for node_id, option_id, starts_at, ends_at, dependencies in specs:
        option = await world.get(option_id)
        assert option is not None
        nodes.append(PlanNode(
            id=node_id,
            capability_id=(
                "dining" if option.vertical.value == "food"
                else "mobility" if option.vertical.value == "mobility"
                else "experiences"
            ),
            vertical=option.vertical,
            title=option.name,
            option_id=option.id,
            starts_at=starts_at,
            ends_at=ends_at,
            price_yuan=option.price_yuan,
            venue=option.venue,
            reason="满足放松、少排队与准时到家的目标",
            trigger_kind=(
                "queue_delay" if option.vertical.value == "food"
                else "eta_delay" if option.vertical.value == "mobility"
                else "inventory_unavailable"
            ),
            actions=option.actions,
            depends_on=dependencies,
            evidence=option.evidence,
        ))
    goal = GoalContract(
        outcome="和朋友轻松度过今晚",
        city="北京",
        origin="国贸",
        party_size=2,
        budget_yuan=500,
        deadline="23:00",
        preferences=["少排队", "适合聊天"],
        constraints=[
            Constraint(
                kind=ConstraintKind.BUDGET,
                label="总预算",
                value="500 元以内",
                hard=True,
                source=ValueSource.EXPLICIT,
            )
        ],
    )
    return PlanGraph(
        title="国贸松弛夜",
        thesis="用短移动串起安静晚餐和喜剧，留出返程缓冲。",
        goal=goal,
        nodes=nodes,
        total_yuan=sum(node.price_yuan for node in nodes),
        rationale=["地点集中", "库存已核验"],
        tradeoffs=["放弃更远但更新奇的手作活动"],
        mandate=ExecutionMandate(
            max_total_yuan=500,
            deadline="23:00",
            allowed_verticals=["food", "activity", "mobility"],
        ),
    )


async def make_policy(world: SupplyTwin) -> PlanPolicy:
    return PlanPolicy(primary_plan=await make_plan(world))
