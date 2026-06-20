import asyncio

from app.agents.planner import RouteAgentRunner, build_route_agent
from app.agents.tools import build_route_tools
from app.domain.constraints import ConstraintEngine


class FakePlanningService:
    _constraint_engine = ConstraintEngine()


def test_builds_a_single_route_agent_with_explicit_grounding_instructions() -> None:
    tools = build_route_tools(FakePlanningService())

    agent = build_route_agent(tools)

    assert agent.name == "route_planner"
    assert len(agent.tools) == 7
    assert "Never invent POIs" in agent.instructions
    assert "deterministic" in agent.instructions


def test_route_agent_runner_protocol_supports_dependency_injected_fakes() -> None:
    class FakeRunner:
        async def run(self, *, query: str, city: str, user_id: str) -> object:
            return {"query": query, "city": city, "userId": user_id}

    async def scenario(runner: RouteAgentRunner) -> None:
        assert await runner.run(query="晚餐", city="上海", user_id="u-1") == {
            "query": "晚餐", "city": "上海", "userId": "u-1"
        }

    asyncio.run(scenario(FakeRunner()))
