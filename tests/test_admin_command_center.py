import asyncio
from pathlib import Path

from app.services.telegram.admin_console import (
    AdminConsoleController,
    is_admin_user,
    render_admin_view,
)


class FakeTG:
    def __init__(self):
        self.sent = []
        self.edited = []
        self.answered = []
        self.deleted = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))

    async def edit_message(self, chat_id, message_id, text, reply_markup=None):
        self.edited.append((chat_id, message_id, text, reply_markup))

    async def answer_callback_query(self, callback_id, text=None, show_alert=False):
        self.answered.append((callback_id, text, show_alert))

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))


class FakeProfiles:
    def get(self, chat_id):
        return {"language": "ru"}


class FakeStore:
    def recovery_status(self):
        return {"primary_available": True, "last_probe_ok": True, "outbox_pending": 0}


DASHBOARD = {
    "schema": "bco-admin-dashboard-v1",
    "users": {"tracked_telegram": 7, "unified_known": 5, "canonical_accounts": 5, "active_24h": 3, "active_7d": 4, "active_30d": 5, "new_24h": 1, "new_7d": 2},
    "activity": {"today_updates": 20, "today_messages": 9, "today_voice": 2, "today_miniapp": 4, "today_miniapp_users": 2, "week_updates": 90, "week_messages": 50, "week_voice": 10, "week_miniapp": 15, "week_miniapp_users": 3, "total_updates": 120, "total_messages": 70, "total_voice": 13, "total_miniapp": 18, "daily_coverage_days": 4},
    "identity": {"accounts": 5, "identities": 6, "resolved": 3, "unresolved": 2, "conflict": 0, "merge_pending": 0, "dual_write": True, "shadow_read": True},
    "premium": {"active_accounts": 1},
    "intel": {"snapshots": 3, "changes": 1, "latest_snapshot_at": "2026-08-20T12:00:00Z", "latest_change_at": "2026-08-20T13:00:00Z"},
}


def test_render_admin_dashboard_has_no_personal_ids():
    text, markup = render_admin_view(DASHBOARD, view="overview", locale="ru", system={"build": {"git_commit_short": "abc123", "exact": True}, "recovery": {"primary_available": True, "last_probe_ok": True, "outbox_pending": 0}})
    assert "Уникальные пользователи — 5" in text
    assert "Active 24h — 3" in text
    assert "Mini App users сегодня — 2" in text
    assert "Число участников в шапке Telegram ≠" in text
    assert "telegram_user_id" not in text
    assert "black_crown_user_id" not in text
    callbacks = [button["callback_data"] for row in markup["inline_keyboard"] for button in row]
    assert "bco:admin:users" in callbacks
    assert "bco:admin:system" in callbacks
    assert "bco:admin:refresh" in callbacks


def test_admin_identity_view_exposes_counts_not_subjects():
    text, _ = render_admin_view(DASHBOARD, view="identity", locale="en")
    assert "Resolved — 3" in text
    assert "Unresolved — 2" in text
    assert "Canonical dual-write — ON" in text
    assert "Canonical shadow-read — ON" in text
    assert "Client owner authority — OFF" in text
    assert "provider_subject" not in text


def test_admin_users_view_distinguishes_miniapp_users_from_events():
    text, _ = render_admin_view(DASHBOARD, view="users", locale="ru")
    assert "Mini App пользователи 24ч — 2" in text
    assert "Mini App пользователи 7д — 3" in text


def test_admin_authority_fails_closed(monkeypatch):
    monkeypatch.delenv("BCO_ADMIN_TELEGRAM_USER_ID", raising=False)
    monkeypatch.delenv("BCO_ADMIN_TELEGRAM_USER_IDS", raising=False)
    assert is_admin_user(42) is False
    monkeypatch.setenv("BCO_ADMIN_TELEGRAM_USER_ID", "42")
    assert is_admin_user(42) is True
    assert is_admin_user(43) is False


def test_owner_command_and_callback_use_one_message(monkeypatch):
    monkeypatch.setenv("BCO_ADMIN_TELEGRAM_USER_ID", "42")
    tg = FakeTG()
    controller = AdminConsoleController(tg=tg, store=FakeStore(), profiles=FakeProfiles())

    async def fake_dashboard():
        return DASHBOARD

    controller._dashboard = fake_dashboard
    message = {"message": {"text": "/admin", "chat": {"id": 42, "type": "private"}, "from": {"id": 42, "language_code": "ru"}}}
    assert asyncio.run(controller.maybe_handle(message)) is True
    assert len(tg.sent) == 1
    assert "ADMIN COMMAND CENTER" in tg.sent[0][1]

    callback = {"callback_query": {"id": "cb1", "data": "bco:admin:users", "from": {"id": 42}, "message": {"message_id": 99, "chat": {"id": 42, "type": "private"}}}}
    assert asyncio.run(controller.maybe_handle(callback)) is True
    assert len(tg.edited) == 1
    assert tg.edited[0][1] == 99
    assert "DAU / 24h — 3" in tg.edited[0][2]


def test_non_admin_callback_never_reveals_dashboard(monkeypatch):
    monkeypatch.setenv("BCO_ADMIN_TELEGRAM_USER_ID", "42")
    tg = FakeTG()
    controller = AdminConsoleController(tg=tg, store=FakeStore(), profiles=FakeProfiles())
    callback = {"callback_query": {"id": "cb2", "data": "bco:admin:system", "from": {"id": 7}, "message": {"message_id": 1, "chat": {"id": 7, "type": "private"}}}}
    assert asyncio.run(controller.maybe_handle(callback)) is True
    assert tg.sent == [] and tg.edited == []
    assert tg.answered == [("cb2", "ADMIN access denied.", True)]


def test_admin_migration_is_server_only_and_additive():
    sql = Path("migrations/011_admin_command_center.sql").read_text(encoding="utf-8").lower()
    assert "create table if not exists public.bco_user_activity_daily" in sql
    assert "bco_admin_dashboard_v1" in sql
    assert "today_miniapp_users" in sql and "week_miniapp_users" in sql
    assert "grant execute on function public.bco_admin_dashboard_v1() to service_role" in sql
    assert "revoke all on function public.bco_admin_dashboard_v1() from public, anon, authenticated" in sql
    assert "drop table" not in sql
    assert "delete from" not in sql
