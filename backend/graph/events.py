from __future__ import annotations

import json
from typing import Any


def sse_event(event_id: str, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"
