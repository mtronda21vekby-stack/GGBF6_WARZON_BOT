from __future__ import annotations

from typing import Any

from app.crown_core.contracts import CrownPrincipal


ALLOWED_ACTION_MEMORY_FIELDS = frozenset(
    {"current_goal", "training_focus", "weekly_focus", "playstyle"}
)


class CrownMemoryActionFailure(ValueError):
    pass


def forget_canonical_memory_field(
    core: Any,
    principal: CrownPrincipal,
    field: str,
) -> dict[str, Any]:
    """Forget one allow-listed user-controlled Player Brain field.

    Ownership is represented by the server-resolved `CrownPrincipal`; callers
    never supply a canonical user id. The current profile store is merge-only,
    so V1 writes an empty tombstone and removes that field from the returned
    product projection. No identity/system field can cross this boundary.
    """

    normalized = str(field or "").strip().lower()
    if normalized not in ALLOWED_ACTION_MEMORY_FIELDS:
        raise CrownMemoryActionFailure("invalid_memory_field")

    profiles = getattr(core, "profiles", None)
    patch = getattr(profiles, "patch", None)
    if not callable(patch):
        raise CrownMemoryActionFailure("memory_mutation_unavailable")

    # Validate ownership against the canonical profile before mutation.
    profile_for = getattr(core, "profile_for", None)
    if not callable(profile_for):
        raise CrownMemoryActionFailure("memory_mutation_unavailable")
    profile_for(principal)

    patch(principal.legacy_owner_id, {normalized: ""})
    snapshot = core.brain_snapshot(principal)
    profile = snapshot.get("profile")
    if isinstance(profile, dict):
        profile = dict(profile)
        profile.pop(normalized, None)
        snapshot = {**snapshot, "profile": profile}
    return snapshot
