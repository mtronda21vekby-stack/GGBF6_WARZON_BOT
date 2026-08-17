from app.i18n import detect_text_locale, normalize_locale, resolve_locale
from app.services.analytics.admin_usage import AdminUsageAnalytics


def test_locale_detection_and_override():
    assert detect_text_locale("I need milk") == "en"
    assert detect_text_locale("Мне нужно молоко") == "ru"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("ru_RU") == "ru"
    raw = {"message": {"from": {"id": 1, "language_code": "en-US"}}}
    assert resolve_locale(raw=raw, profile={}, text="") == "en"
    assert resolve_locale(raw=raw, profile={"language_override": "ru"}, text="I need milk") == "ru"
    assert resolve_locale(raw=raw, profile={}, text="Мне нужно молоко") == "ru"


def test_admin_report_is_aggregate_only():
    report = AdminUsageAnalytics.render({"total_users": 11, "active_24h": 3, "active_7d": 8, "active_30d": 11, "new_24h": 1, "new_7d": 4, "total_updates": 99, "total_messages": 50, "total_voice": 7, "total_miniapp": 9}, "en")
    assert "TOTAL TRACKED USERS — 11" in report
    assert "ACTIVE 24H — 3" in report
    assert "Telegram header member counts are not bot MAU/DAU analytics" in report
    assert "telegram_user_id" not in report
