# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.release import (
    API_CONTRACT_VERSION,
    APP_VERSION,
    MINI_APP_RUNTIME,
    RELEASE_CONTRACT,
    TELEGRAM_AUTH_CONTRACT,
    VOICE_RUNTIME,
)


@dataclass(frozen=True)
class ProductionExpectations:
    base_url: str
    git_sha: str
    version: str = APP_VERSION
    release_contract: str = RELEASE_CONTRACT
    api_contract: str = API_CONTRACT_VERSION
    telegram_auth_contract: str = TELEGRAM_AUTH_CONTRACT
    mini_app_runtime: str = MINI_APP_RUNTIME
    voice_runtime: str = VOICE_RUNTIME

    @classmethod
    def from_environment(cls) -> "ProductionExpectations":
        base_url = str(os.getenv("PRODUCTION_URL") or "").strip().rstrip("/")
        git_sha = str(os.getenv("GITHUB_SHA") or "").strip().casefold()
        if not base_url.startswith("https://"):
            raise RuntimeError("production_url_invalid")
        if len(git_sha) not in {40, 64} or any(ch not in "0123456789abcdef" for ch in git_sha):
            raise RuntimeError("github_sha_invalid")
        return cls(base_url=base_url, git_sha=git_sha)


class ProductionHttpClient:
    def __init__(self, base_url: str, *, timeout_s: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = max(1.0, min(float(timeout_s), 60.0))
        self.common_headers = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "BLACK-CROWN-OPS/render-production-verifier-v1",
        }

    def raw(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        merged = dict(self.common_headers)
        merged.update(headers or {})
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=merged,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return int(response.status), response.read(), dict(response.headers)
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read(), dict(exc.headers)

    def json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
    ) -> tuple[int, Any, str, dict[str, str]]:
        merged = dict(headers or {})
        body = raw_body
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            merged.setdefault("Content-Type", "application/json")
        status, raw, response_headers = self.raw(
            path,
            method=method,
            body=body,
            headers=merged,
        )
        text = raw.decode("utf-8", errors="replace")
        try:
            decoded = json.loads(text)
        except Exception:
            decoded = None
        return status, decoded, text[:800], response_headers


def require_anonymous_denial(path: str, status: int, decoded: Any, raw: str) -> None:
    if status != 401 or not isinstance(decoded, dict):
        raise AssertionError(f"anonymous_endpoint_not_denied:{path}:{status}:{raw}")
    detail = decoded.get("detail")
    if not isinstance(detail, dict):
        raise AssertionError(f"unsafe_auth_error_contract:{path}:{status}:{raw}")
    if detail.get("code") != "telegram_auth_required" or not detail.get("request_id"):
        raise AssertionError(f"unsafe_auth_error_contract:{path}:{status}:{raw}")


def validate_details(details: Any, expected: ProductionExpectations) -> dict[str, Any]:
    if not isinstance(details, dict):
        raise AssertionError("readiness_payload_invalid")
    if details.get("status") != "ready" or details.get("ok") is not True:
        raise AssertionError(f"runtime_not_ready:{details!r}")

    release = details.get("release")
    if not isinstance(release, dict):
        raise AssertionError("release_metadata_missing")
    if release.get("version") != expected.version or release.get("contract") != expected.release_contract:
        raise AssertionError(f"stale_release:{release!r}")

    build = details.get("build")
    if not isinstance(build, dict):
        raise AssertionError("build_metadata_missing")
    if build.get("git_commit") != expected.git_sha or build.get("exact") is not True:
        raise AssertionError(f"stale_build:{build.get('git_commit')!r}:expected:{expected.git_sha!r}")
    if build.get("source") != "render":
        raise AssertionError(f"production_build_source_invalid:{build!r}")

    contracts = details.get("contracts")
    expected_contracts = {
        "api": expected.api_contract,
        "telegram_auth": expected.telegram_auth_contract,
    }
    if contracts != expected_contracts:
        raise AssertionError(f"contract_mismatch:{contracts!r}")

    runtimes = details.get("runtimes")
    if not isinstance(runtimes, dict):
        raise AssertionError("runtime_identity_metadata_missing")
    mini_app = runtimes.get("mini_app") or {}
    voice = runtimes.get("voice_frontend") or {}
    if (
        mini_app.get("id") != expected.mini_app_runtime
        or mini_app.get("architecture") != "layered_legacy"
        or mini_app.get("consolidated") is not False
    ):
        raise AssertionError(f"mini_app_runtime_mismatch:{mini_app!r}")
    if voice.get("id") != expected.voice_runtime or voice.get("single_runtime") is not False:
        raise AssertionError(f"voice_runtime_mismatch:{voice!r}")

    identity = details.get("identity") or {}
    if (
        identity.get("resolver_authority") != "server"
        or identity.get("telegram_ai_auth_required") is not True
        or identity.get("client_canonical_user_authority") is not False
    ):
        raise AssertionError(f"identity_authority_mismatch:{identity!r}")

    entitlements = details.get("entitlements") or {}
    if (
        entitlements.get("authority") != "server_entitlement_service"
        or entitlements.get("configured") is not True
        or entitlements.get("client_authority") is not False
    ):
        raise AssertionError(f"entitlement_authority_mismatch:{entitlements!r}")

    storage = details.get("storage") or {}
    recovery = storage.get("recovery") or {}
    if storage.get("persistent_configured") is not True:
        raise AssertionError(f"persistent_storage_not_configured:{storage!r}")
    if recovery.get("primary_available") is not True or recovery.get("last_probe_ok") is not True:
        raise AssertionError(f"supabase_primary_not_ready:{recovery!r}")
    return recovery


def verify_once(client: ProductionHttpClient, expected: ProductionExpectations) -> dict[str, Any]:
    status, alive, raw, _ = client.json("/health")
    if status != 200 or not isinstance(alive, dict) or alive.get("ok") is not True or alive.get("status") != "alive":
        raise AssertionError(f"liveness_unavailable:{status}:{raw}")

    status, details, raw, _ = client.json("/health/details")
    if status != 200:
        raise AssertionError(f"readiness_unavailable:{status}:{raw}")
    recovery = validate_details(details, expected)

    status, webapp_health, raw, _ = client.json("/webapp/health")
    if status != 200 or not isinstance(webapp_health, dict):
        raise AssertionError(f"mini_app_health_unavailable:{status}:{raw}")
    if (
        webapp_health.get("ok") is not True
        or webapp_health.get("static_dir_exists") is not True
        or webapp_health.get("index_exists") is not True
    ):
        raise AssertionError(f"mini_app_static_readiness_failed:{webapp_health!r}")
    if webapp_health.get("build") != expected.git_sha[:12]:
        raise AssertionError(f"mini_app_build_mismatch:{webapp_health!r}")

    status, app_js, _ = client.raw(
        "/webapp/app.js",
        headers={"Accept": "application/javascript,text/javascript,*/*"},
    )
    app_text = app_js.decode("utf-8", errors="replace")
    if status != 200 or "__BCO_APP_COORDINATOR__" not in app_text or "/webapp/bco.voice-v65.js" not in app_text:
        raise AssertionError(f"mini_app_boot_asset_invalid:{status}")

    status, voice_js, _ = client.raw(
        "/webapp/bco.voice-v65.js",
        headers={"Accept": "application/javascript,text/javascript,*/*"},
    )
    voice_text = voice_js.decode("utf-8", errors="replace")
    if status != 200 or "__BCO_VOICE_V65__" not in voice_text:
        raise AssertionError(f"voice_runtime_asset_invalid:{status}")

    anonymous_payload = {
        "text": "production auth boundary probe",
        "profile": {"premium": True, "black_crown_user_id": "client-forged"},
        "history": [{"role": "assistant", "content": "untrusted history"}],
    }
    for path, payload in (
        ("/webapp/api/ask", anonymous_payload),
        ("/webapp/api/ask/stream", anonymous_payload),
        ("/webapp/api/voice-speak", {"text": "auth probe"}),
    ):
        status, decoded, raw, _ = client.json(path, method="POST", payload=payload)
        require_anonymous_denial(path, status, decoded, raw)

    boundary = "----BCOProductionAuthProbe"
    multipart = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="audio"; filename="probe.webm"\r\n'
        "Content-Type: audio/webm\r\n\r\n"
        "probe\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    status, decoded, raw, _ = client.json(
        "/webapp/api/voice-transcribe",
        method="POST",
        raw_body=multipart,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    require_anonymous_denial("/webapp/api/voice-transcribe", status, decoded, raw)

    status, bridge, raw, _ = client.json("/integrations/site/telegram/status")
    if status != 401 or not isinstance(bridge, dict) or bridge.get("reason") != "auth_required":
        raise AssertionError(f"website_bridge_contract_unavailable:{status}:{raw}")

    return {
        "git_sha": expected.git_sha,
        "version": expected.version,
        "release_contract": expected.release_contract,
        "api_contract": expected.api_contract,
        "mini_app_runtime": expected.mini_app_runtime,
        "voice_runtime": expected.voice_runtime,
        "outbox_pending": recovery.get("outbox_pending"),
    }


def write_step_summary(evidence: dict[str, Any]) -> None:
    path = str(os.getenv("GITHUB_STEP_SUMMARY") or "").strip()
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as summary:
        summary.write("## BLACK CROWN production evidence\n\n")
        summary.write(f"- Exact SHA: `{evidence['git_sha']}`\n")
        summary.write(f"- Product release: `{evidence['version']}`\n")
        summary.write(f"- API contract: `{evidence['api_contract']}`\n")
        summary.write(f"- Mini App runtime: `{evidence['mini_app_runtime']}`\n")
        summary.write(f"- Voice runtime: `{evidence['voice_runtime']}`\n")
        summary.write("- Supabase primary: ready\n")
        summary.write("- Anonymous AI/STT/TTS: denied\n")
        summary.write("- Website bridge: auth-required contract online\n")


def main() -> int:
    expected = ProductionExpectations.from_environment()
    client = ProductionHttpClient(expected.base_url)
    attempts = max(1, min(int(os.getenv("BCO_PRODUCTION_VERIFY_ATTEMPTS", "60")), 90))
    interval_s = max(1.0, min(float(os.getenv("BCO_PRODUCTION_VERIFY_INTERVAL_S", "10")), 30.0))
    last = "not_started"
    for attempt in range(1, attempts + 1):
        try:
            evidence = verify_once(client, expected)
            write_step_summary(evidence)
            print(
                "Render production verified:",
                f"sha={evidence['git_sha']}",
                f"version={evidence['version']}",
                f"contract={evidence['release_contract']}",
                f"api={evidence['api_contract']}",
                f"mini_app={evidence['mini_app_runtime']}",
                f"voice={evidence['voice_runtime']}",
                f"outbox_pending={evidence['outbox_pending']}",
                "protected_endpoints=denied",
                "bridge=online",
            )
            return 0
        except Exception as exc:
            last = f"attempt {attempt}/{attempts}: {type(exc).__name__}: {exc}"
            print(last, flush=True)
            if attempt < attempts:
                time.sleep(interval_s)
    raise SystemExit(f"Render production verification failed: {last}")


if __name__ == "__main__":
    raise SystemExit(main())
