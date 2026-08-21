from __future__ import annotations

from uuid import UUID

from app.services.profiles.service import ProfileService
from app.services.storage.factory import PersistentResilientStore
from app.services.storage.memory import InMemoryStore


OWNER = str(UUID("11111111-1111-1111-1111-111111111111"))


class CanonicalPrimary:
    def get_profile(self, chat_id: int):
        assert chat_id == 42
        return {"game": "Warzone"}

    def resolve_telegram_identity(self, telegram_user_id: int):
        assert telegram_user_id == 42
        return {
            "black_crown_user_id": OWNER,
            "identity_status": "active",
            "account_status": "active",
        }


def test_profile_service_resolves_identity_through_resilient_store():
    store = PersistentResilientStore(
        primary=CanonicalPrimary(),
        fallback=InMemoryStore(),
    )
    profile = ProfileService(store).get(42)

    assert profile["game"] == "Warzone"
    assert profile["black_crown_user_id"] == OWNER
    assert profile["crown_identity_status"] == "active"
    assert profile["crown_account_status"] == "active"
