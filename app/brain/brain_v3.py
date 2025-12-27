from dataclasses import dataclass
from .memory import MemoryStore, UserState

@dataclass
class BrainReply:
    text: str

class BrainV3:
    """
    “Премиум мозг” — тут будет:
    - роутинг по режимам (игра/стиль/профиль/зомби/вод)
    - инструменты
    - память
    - ИИ-ответы
    """
    def __init__(self, mem: MemoryStore):
        self.mem = mem

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        st = self.mem.get(user_id)
        st.turns += 1
        st.last_topic = (text[:120] or "").strip()
        self.mem.set(user_id, st)

        # Заглушка: сюда подключим OpenAI и нормальную логику
        return BrainReply(text=f"🧠 Brain v3: понял. Ты написал: {text}")

    def set_style(self, user_id: int, style: str):
        st = self.mem.get(user_id)
        st.style = style
        self.mem.set(user_id, st)
