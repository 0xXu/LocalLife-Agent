import asyncio
from dataclasses import dataclass

from app.application.profiles import SessionService


@dataclass
class Session:
    id: str
    user_id: str


class FakeSessions:
    def __init__(self, items: dict[str, Session]) -> None:
        self.items = items

    async def get(self, session_id: str, user_id: str) -> Session | None:
        session = self.items.get(session_id)
        return session if session and session.user_id == user_id else None


def test_nonowner_session_lookup_returns_none() -> None:
    async def scenario() -> None:
        service = SessionService(FakeSessions({"session-1": Session("session-1", "owner")}))

        assert await service.get("session-1", "intruder") is None

    asyncio.run(scenario())

