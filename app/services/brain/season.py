# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SeasonManager:
    season_id: str = "S1"

    @staticmethod
    def make_new_season_id() -> str:
        # Например: S2025-12
        now = datetime.now(timezone.utc)
        return f"S{now.year}-{now.month:02d}"

    def reset_season(self):
        self.season_id = self.make_new_season_id()
