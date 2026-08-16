# BLACK CROWN OPS v14 — Telegram Tactical UI

## Objective

Reduce Telegram interface density and make the bot feel like a coherent FPS command system rather than a grid of unrelated utility buttons.

Telegram owns the native keyboard colors and button chrome. This release therefore improves the parts controlled by the bot:

- information architecture;
- button hierarchy;
- menu density;
- input placeholders;
- response-card typography;
- Premium/account visual consistency;
- destructive-action placement.

## Main command deck

The main keyboard is now a consistent two-column deck:

1. AI and Training;
2. Game and VOD;
3. Zombies and Profile;
4. Premium and Settings;
5. Status and Command Center.

Memory clearing and full reset are no longer exposed on the primary screen. They remain available inside Settings.

## Compatibility

Existing command labels are preserved for routed actions. Users with an older cached Telegram keyboard can continue using the old buttons while the next bot response replaces the keyboard with the v14 deck.

The configured WebApp button is branded as `COMMAND CENTER`; the legacy `MINI APP` text fallback remains available when no WebApp URL is configured.

## Tactical cards

Legacy responses used a double heavy frame and repeated `BCO` signature. The Telegram adapter now converts those messages into one compact plain-text card:

```text
◼ BLACK CROWN OPS // TEAMMATE
──────────────
Actionable response body
```

No Telegram parse mode is required, so model output and user-provided content are not exposed to HTML/Markdown escaping problems.

The long legacy `/start` manifesto is converted at the presentation boundary into fast onboarding with three example requests.

Premium and account-link panels use the same card language.

## Safety

- destructive actions are nested, not removed;
- no routing or gameplay capability is deleted;
- no token, key or Supabase state is changed;
- no external service is added;
- browser and Telegram account-link authority remain unchanged.

## Validation

Tests cover:

- two-column keyboard limits;
- hidden destructive actions on the main deck;
- role/settings accessibility;
- configured Command Center WebApp button;
- Telegram button/placeholder limits;
- legacy-frame conversion;
- compact onboarding;
- Premium-card consistency.
