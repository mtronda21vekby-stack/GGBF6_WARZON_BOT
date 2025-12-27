# -*- coding: utf-8 -*-
from __future__ import annotations
from app.services.brain.memory import InMemoryStore

class ProfileService:
    def __init__(self, store: InMemoryStore):
        self.store = store

    def get_profile(self, user_id: int):
        st = self.store.get(user_id)
        return {"game": st.game, "style": st.style}

    def set_game(self, user_id: int, game: str) -> None:
        st = self.store.get(user_id)
        st.game = game

    def set_style(self, user_id: int, style: str) -> None:
        st = self.store.get(user_id)
        st.style = style
