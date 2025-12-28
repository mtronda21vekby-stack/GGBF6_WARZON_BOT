from app.core.outgoing import Outgoing
from app.ui.keyboards import KB
from app.domain.devices import Device


def select_device(profiles, user_id: int, device: Device) -> Outgoing:
    p = profiles.get(user_id)
    p.device = device

    return Outgoing(
        text=f"🕹 Устройство: {device.value.upper()}",
        inline_keyboard=KB.settings_difficulty(),
        ensure_quickbar=True,
    )
