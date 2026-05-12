from backend.actions.ledger import ledger_from_actions
from backend.models.schemas import PlanAction


def test_ledger_executes_only_selected_actions_once():
    actions = [
        PlanAction("message", "发送计划", "同行人", "发送摘要", True, "send_plan_message", {"recipient": "同行人"}),
        PlanAction("calendar", "创建日历", "本地日历", "创建提醒", True, "create_calendar_event", {"participants": 1}),
    ]
    ledger = ledger_from_actions("plan_1", actions)
    selected = [ledger.entries[0].action_id]

    executed = ledger.mark_executing(selected, idempotency_key="idem_1")
    repeated = ledger.mark_executing(selected, idempotency_key="idem_1")

    assert [entry.action_id for entry in executed] == selected
    assert repeated == []
    assert ledger.entries[0].status == "executing"
    assert ledger.entries[1].status == "pending"
