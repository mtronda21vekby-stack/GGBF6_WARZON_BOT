# -*- coding: utf-8 -*-
import re

CHEAT_PATTERNS = [
    r"\bчит\b", r"\bчиты\b", r"\bhack\b", r"\bhacks\b", r"\bаимбот\b", r"\bwallhack\b",
    r"\bспуф\b", r"\bspoof\b", r"\bunlock\b", r"\bразбан\b", r"\bобход\b.*античит",
]

TILT_PATTERNS = [
    r"\bтильт\b", r"\bгорит\b", r"\bбесит\b", r"\bзаебал\b", r"\bненавижу\b",
]

SMALLTALK_PATTERNS = [
    r"^привет\b", r"^йо\b", r"^ку\b", r"как дела", r"кто ты", r"что ты умеешь",
]

def is_cheat_request(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in CHEAT_PATTERNS)

def is_tilt(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in TILT_PATTERNS)

def is_smalltalk(text: str) -> bool:
    t = (text or "").lower().strip()
    return any(re.search(p, t) for p in SMALLTALK_PATTERNS)