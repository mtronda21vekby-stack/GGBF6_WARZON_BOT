import json

import httpx

from app.services.storage.factory import PersistentSupabaseStore


def test_supabase_profile_patch_uses_server_authenticated_rpc():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(204, request=request)

    store = PersistentSupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    store._client.close()
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        store.set_profile(123, {"rank": "Diamond"})
        assert len(seen) == 1
        request = seen[0]
        assert request.url.path.endswith("/rest/v1/rpc/bco_patch_profile")
        assert request.headers["authorization"] == "Bearer server-secret"
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"p_chat_id": 123, "p_patch": {"rank": "Diamond"}}
    finally:
        store.close()


def test_supabase_purge_uses_dedicated_server_rpc():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(204, request=request)

    store = PersistentSupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    store._client.close()
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        store.purge_player(7)
        assert seen[0].url.path.endswith("/rest/v1/rpc/bco_purge_player")
        assert json.loads(seen[0].content.decode("utf-8")) == {"p_chat_id": 7}
    finally:
        store.close()
