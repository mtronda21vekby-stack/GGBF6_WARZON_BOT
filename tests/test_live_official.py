from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeConfidence, KnowledgeRequest
from app.services.brain.live_official import OfficialPatchKnowledgeProvider


COD_INDEX = "https://www.callofduty.com/patchnotes"
BF_INDEX = "https://www.ea.com/games/battlefield/battlefield-6/news"
WZ = "https://www.callofduty.com/patchnotes/2026/07/call-of-duty-bo7-warzone-season-05-patch-notes"
BO7 = "https://www.callofduty.com/patchnotes/2026/07/call-of-duty-black-ops-7-season-05-patch-notes"
BF6 = "https://www.ea.com/games/battlefield/battlefield-6/news/battlefield-6-game-update-1-4-1-0"


INDEX_HTML = f"""
<html><body>
<a href="/patchnotes/2026/07/call-of-duty-bo7-warzone-season-05-patch-notes">Call of Duty: Warzone Season 05 Patch Notes</a>
<a href="/patchnotes/2026/07/call-of-duty-black-ops-7-season-05-patch-notes">Call of Duty: Black Ops 7 Season 05 Patch Notes</a>
</body></html>
"""

BF_INDEX_HTML = """
<html><body>
<a href="/games/battlefield/battlefield-6/news/battlefield-6-game-update-1-4-1-0">BATTLEFIELD 6 GAME UPDATE 1.4.1.0</a>
</body></html>
"""

WZ_HTML = """
<html><body><h1>Call of Duty: Warzone Season 05 Patch Notes</h1><p>July 22, 2026</p>
<h2>WEAPONS</h2><li>Mammoth LMG damage range increased.</li><li>Example SMG recoil adjusted.</li></body></html>
"""

BO7_HTML = """
<html><body><h1>Call of Duty: Black Ops 7 Season 05 Patch Notes</h1><p>July 23, 2026</p>
<h2>MULTIPLAYER</h2><li>Weapon handling was adjusted for Multiplayer.</li></body></html>
"""

BF6_HTML = """
<html><body><h1>BATTLEFIELD 6 GAME UPDATE 1.4.1.0</h1><p>July 16, 2026</p>
<h2>MAJOR UPDATES</h2><li>Weapons and vehicles received balance improvements.</li></body></html>
"""


def _request(game: str, intent: Intent = Intent.PATCH_CURRENT, text: str = "последний патч"):
    return KnowledgeRequest(
        intent=IntentResult(intent, 0.99, needs_current_data=True),
        text=text,
        profile={"game": game},
    )


def _fetcher(counter=None):
    pages = {
        COD_INDEX: (COD_INDEX, INDEX_HTML),
        BF_INDEX: (BF_INDEX, BF_INDEX_HTML),
        WZ: (WZ, WZ_HTML),
        BO7: (BO7, BO7_HTML),
        BF6: (BF6, BF6_HTML),
    }

    def fetch(url):
        if counter is not None:
            counter.append(url)
        return pages[url]

    return fetch


def test_warzone_live_official_patch_is_verified_current():
    provider = OfficialPatchKnowledgeProvider(fetcher=_fetcher())
    ctx = provider.query(_request("Warzone", Intent.META_CURRENT, "какая сейчас мета оружия"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert ctx.source == WZ
    assert ctx.last_updated == "2026-07-22"
    assert any("Mammoth LMG" in fact.text for fact in ctx.facts)


def test_bo7_does_not_accidentally_select_warzone_article():
    provider = OfficialPatchKnowledgeProvider(fetcher=_fetcher())
    ctx = provider.query(_request("BO7"))
    assert ctx.source == BO7
    assert ctx.last_updated == "2026-07-23"


def test_bf6_uses_ea_game_update_index():
    provider = OfficialPatchKnowledgeProvider(fetcher=_fetcher())
    ctx = provider.query(_request("BF6"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert ctx.source == BF6
    assert "1.4.1.0" in ctx.facts[0].text


def test_live_document_cache_avoids_repeated_network_fetches():
    calls = []
    provider = OfficialPatchKnowledgeProvider(fetcher=_fetcher(calls), ttl_s=900)
    provider.query(_request("Warzone"))
    provider.query(_request("Warzone", Intent.META_CURRENT, "мета сейчас"))
    assert calls == [COD_INDEX, WZ]


def test_redirect_outside_allowlist_fails_closed():
    def bad_fetch(url):
        return "https://evil.example/patchnotes", INDEX_HTML

    provider = OfficialPatchKnowledgeProvider(fetcher=bad_fetch)
    ctx = provider.query(_request("Warzone"))
    assert ctx.confidence == KnowledgeConfidence.UNKNOWN
    assert ctx.facts == []
