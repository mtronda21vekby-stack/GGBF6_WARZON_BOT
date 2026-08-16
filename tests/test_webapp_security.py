import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.webapp.security import verify_init_data
from app.webapp.webapp_router import _is_safe_rel_path


def _signed_init_data(token: str) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AA-test",
        "user": json.dumps({"id": 12345, "first_name": "Test"}, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={values[k]}" for k in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_init_data_valid_and_extracts_identity():
    token = "123456:TEST_TOKEN"
    ok, meta = verify_init_data(_signed_init_data(token), token=token)
    assert ok is True
    assert meta["user_id"] == 12345


def test_init_data_rejects_tampering():
    token = "123456:TEST_TOKEN"
    raw = _signed_init_data(token).replace("Test", "Hacker")
    ok, _ = verify_init_data(raw, token=token)
    assert ok is False


def test_static_path_traversal_blocked():
    assert _is_safe_rel_path("style.css") is True
    assert _is_safe_rel_path("assets/logo.png") is True
    assert _is_safe_rel_path("../secret") is False
    assert _is_safe_rel_path("/etc/passwd") is False
