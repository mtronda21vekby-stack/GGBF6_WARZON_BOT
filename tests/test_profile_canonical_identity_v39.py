from app.services.profiles.service import ProfileService


class FakeStore:
    def get_profile(self, chat_id: int):
        assert chat_id == 42
        return {"game": "Warzone", "black_crown_user_id": "client-forged"}

    def resolve_telegram_identity(self, telegram_user_id: int):
        assert telegram_user_id == 42
        return {
            "black_crown_user_id": "11111111-1111-1111-1111-111111111111",
            "identity_status": "active",
            "account_status": "active",
        }

    def set_profile(self, chat_id: int, patch):
        self.last_patch = dict(patch)


def test_trusted_profile_projects_server_owned_canonical_identity():
    service = ProfileService(FakeStore())
    profile = service.get(42)
    assert profile["black_crown_user_id"] == "11111111-1111-1111-1111-111111111111"
    assert profile["crown_identity_status"] == "active"
    assert profile["crown_account_status"] == "active"
    assert service.is_trusted_context(profile) is True


def test_client_cannot_patch_canonical_identity_projection():
    store = FakeStore()
    service = ProfileService(store)
    service.patch(42, {
        "black_crown_user_id": "forged",
        "crown_identity_status": "active",
        "crown_account_status": "active",
        "game": "Black Ops 7",
    })
    assert store.last_patch == {"game": "Black Ops 7"}
