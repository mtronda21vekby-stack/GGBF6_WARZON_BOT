from app.services.identity import CrownIdentityCore


class FakeStorage:
    def resolve_telegram_identity(self, telegram_user_id: int):
        assert telegram_user_id == 42
        return {
            "black_crown_user_id": "11111111-1111-1111-1111-111111111111",
            "identity_status": "provisional",
            "account_status": "provisional",
        }


def test_telegram_resolves_to_canonical_black_crown_user_id():
    identity = CrownIdentityCore(FakeStorage()).resolve_telegram(42)
    assert identity is not None
    assert identity.black_crown_user_id == "11111111-1111-1111-1111-111111111111"
    assert identity.provider == "telegram"
    assert identity.provisional is True


def test_identity_core_is_additive_when_storage_has_no_resolver():
    assert CrownIdentityCore(object()).resolve_telegram(42) is None
