from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models.schemas import PlanState
from backend.tools import ExecutionTool


class ExecutionAgent(BaseAgent):
    name = "ExecutionAgent"
    tool = "create_reservation"

    def __init__(self, execution_tool: ExecutionTool) -> None:
        self.execution_tool = execution_tool

    def execute(self, state: PlanState) -> PlanState:
        state.receipts = self.execution_tool.execute(state)
        state.status = "executed"
        return state

    def message(self, state: PlanState) -> str:
        return "用户确认后完成活动预约、餐厅订座和计划发送。"

