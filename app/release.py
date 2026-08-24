# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

APP_VERSION = "44.0.0"
RELEASE_CONTRACT = "bco-aaa-war-room-alerts-v44"

# Product version and deploy/build identity are deliberately separate. These
# values describe the current production boot truth; they do not imply that the
# layered Mini App runtime has already been consolidated.
API_CONTRACT_VERSION = "webapp-api-v1"
CROWN_CORE_VERSION = "crown-core-v1"
NATIVE_API_CONTRACT_VERSION = "crown-native-api-v1"
CROWN_REALTIME_PROTOCOL = "crown-realtime-v1"
TELEGRAM_AUTH_CONTRACT = "telegram-init-data-v1"
MINI_APP_RUNTIME = "bco-layered-runtime-v65"
VOICE_RUNTIME = "bco.voice-v65"
BUILD_METADATA_SCHEMA = "bco-build-v1"

_FULL_GIT_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9._/@+-]{1,128}$")


def runtime_build_metadata(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a privacy-safe exact build identity for health/readiness output.

    Render exposes the deployed source commit as ``RENDER_GIT_COMMIT``. GitHub
    Actions and local release verification can use ``GITHUB_SHA``. Invalid,
    shortened or absent values fail closed to ``unknown`` rather than claiming
    an exact deploy that cannot be proven.
    """

    env = os.environ if environ is None else environ
    commit = "unknown"
    source = "unavailable"
    for candidate_source, name in (
        ("render", "RENDER_GIT_COMMIT"),
        ("github", "GITHUB_SHA"),
        ("source", "SOURCE_COMMIT"),
    ):
        raw = str(env.get(name, "") or "").strip().casefold()
        if _FULL_GIT_SHA.fullmatch(raw):
            commit = raw
            source = candidate_source
            break

    branch = "unknown"
    for name in ("RENDER_GIT_BRANCH", "GITHUB_REF_NAME"):
        raw = str(env.get(name, "") or "").strip()
        if _SAFE_REF.fullmatch(raw):
            branch = raw
            break

    exact = commit != "unknown"
    return {
        "schema": BUILD_METADATA_SCHEMA,
        "git_commit": commit,
        "git_commit_short": commit[:12] if exact else "unknown",
        "source": source,
        "branch": branch,
        "exact": exact,
    }
