from types import SimpleNamespace

from app.services.storage.factory import PersistentResilientStore, build_store
from app.services.storage.memory import InMemoryStore


def _settings(**overrides):
    base = dict(
        memory_max_turns=20,
        storage_backend="auto",
        storage_timeout_s=8.0,
        supabase_url="",
        supabase_service_role_key="",
        supabase_schema="public",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_auto_storage_without_secrets_is_memory():
    assert isinstance(build_store(_settings()), InMemoryStore)


def test_supabase_configuration_builds_resilient_backend_without_network_call():
    store = build_store(_settings(
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-secret-not-real",
    ))
    try:
        assert isinstance(store, PersistentResilientStore)
        assert isinstance(store.fallback, InMemoryStore)
    finally:
        store.close()


def test_incomplete_explicit_supabase_config_falls_back_to_memory():
    store = build_store(_settings(storage_backend="supabase", supabase_url="https://example.supabase.co"))
    assert isinstance(store, InMemoryStore)
