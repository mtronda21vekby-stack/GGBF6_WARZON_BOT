from app.config import Settings


def health_text(settings: Settings) -> str:
    return (
        "✅ Bot is OK\n"
        f"Model: {settings.openai_model}\n"
        f"Admins: {len(settings.admin_ids)}\n"
    )