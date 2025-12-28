# app/core/outgoing.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Outgoing:
    text: str
    keyboard: dict | None = None
