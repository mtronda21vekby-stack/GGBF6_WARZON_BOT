from __future__ import annotations

from uuid import uuid4

import pytest

from app.crown_core.contracts import CrownPrincipal
from app.crown_core.memory_actions import (
    CrownMemoryActionFailure,
    forget_canonical_memory_field,
)


class _Profiles:
    def __init__(self, profile):
        self.profile = dict(profile)
        self.patches: list[tuple[int, dict]] = []

    def patch(self, owner_id: int, patch: dict):
        self.patches.append((owner_id, dict(patch)))
        self.profile.update(patch)


class _Core:
    def __init__(self, principal: CrownPrincipal):
        self.expected = principal
        self.profiles = _Profiles(
            {
                "black_crown_user_id": str(principal.black_crown_user_id),
                "current_goal": "Reach ranked target",
                "playstyle": "aggressive",
            }
        )

    def profile_for(self, principal: CrownPrincipal):
        if principal != self.expected:
            raise RuntimeError("canonical_identity_mismatch")
        return dict(self.profiles.profile)

    def brain_snapshot(self, principal: CrownPrincipal):
        profile = self.profile_for(principal)
        profile.pop("black_crown_user_id", None)
        return {"profile": profile, "summary": "", "derived": {}}


def _principal() -> CrownPrincipal:
    return CrownPrincipal(uuid4(), "apple", str(uuid4()), 77)


def test_forget_canonical_memory_field_uses_allowlisted_tombstone_and_hides_it():
    principal = _principal()
    core = _Core(principal)

    snapshot = forget_canonical_memory_field(core, principal, "current_goal")

    assert core.profiles.patches == [(77, {"current_goal": ""})]
    assert "current_goal" not in snapshot["profile"]
    assert snapshot["profile"]["playstyle"] == "aggressive"


def test_forget_canonical_memory_field_rejects_unknown_key_without_mutation():
    principal = _principal()
    core = _Core(principal)

    with pytest.raises(CrownMemoryActionFailure, match="invalid_memory_field"):
        forget_canonical_memory_field(core, principal, "black_crown_user_id")

    assert core.profiles.patches == []


def test_forget_canonical_memory_field_checks_canonical_ownership_before_mutation():
    owner = _principal()
    attacker = CrownPrincipal(uuid4(), "apple", str(uuid4()), owner.legacy_owner_id)
    core = _Core(owner)

    with pytest.raises(RuntimeError, match="canonical_identity_mismatch"):
        forget_canonical_memory_field(core, attacker, "playstyle")

    assert core.profiles.patches == []
