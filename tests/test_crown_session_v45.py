import asyncio

from app.services.crown_session import CrownSessionService


CANONICAL = "11111111-1111-1111-1111-111111111111"


class Store:
    def resolve_telegram_identity(self, telegram_user_id):
        assert telegram_user_id == 42
        return {"black_crown_user_id": CANONICAL, "identity_status": "active", "account_status": "active"}

    def get_summary(self, chat_id): return "Fast controller player"
    def get_derived_intelligence(self, chat_id): return {"trends": {}}
    def list_mistake_stats(self, chat_id): return [{"label": "late rotation", "count": 3}]
    def list_training_sessions(self, chat_id): return []
    def list_progression_events(self, chat_id, *args): return []
    def list_episodes(self, chat_id, *args): return []
    def stats(self, chat_id): return {"backend": "test"}


class Profiles:
    def get(self, chat_id):
        return {"game": "Warzone", "input": "Controller", "_black_crown_user_id": CANONICAL}


class Status:
    linked = True
    premium = True
    entitlements = ("bco_premium",)
    linked_at = "2026-08-19T00:00:00+00:00"


class Entitlements:
    async def get_status(self, telegram_user_id):
        assert telegram_user_id == 42
        return Status()


def test_crown_session_projects_one_canonical_player_state():
    session = asyncio.run(CrownSessionService(store=Store(), profiles=Profiles(), entitlements=Entitlements()).snapshot(chat_id=42, telegram_user_id=42))
    assert session["schema"] == "crown-session-v1"
    assert session["identity"]["black_crown_user_id"] == CANONICAL
    assert session["identity"]["canonical"] is True
    assert session["profile"]["game"] == "Warzone"
    assert session["personal_meta"]["summary"] == "Fast controller player"
    assert session["entitlement"]["premium"] is True
    assert session["entitlement"]["authority"] == "server"
    assert "mission" in session
    assert "operator_twin" in session


def test_crown_session_fails_closed_when_entitlement_authority_is_unavailable():
    class BrokenEntitlements:
        async def get_status(self, telegram_user_id):
            raise RuntimeError("down")

    session = asyncio.run(CrownSessionService(store=Store(), profiles=Profiles(), entitlements=BrokenEntitlements()).snapshot(chat_id=42, telegram_user_id=42))
    assert session["entitlement"]["state"] == "unavailable"
    assert session["entitlement"]["premium"] is False
