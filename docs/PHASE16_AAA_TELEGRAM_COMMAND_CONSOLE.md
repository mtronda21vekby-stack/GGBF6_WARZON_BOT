# BLACK CROWN OPS v16 — AAA Telegram Command Console

## Objective

Replace the standard persistent Telegram bottom keyboard with an inline, stateful command surface that behaves like a premium product console.

The design remains inside supported Telegram primitives:

- Rich Messages for BLACK CROWN cards;
- styled inline buttons;
- callback navigation;
- in-place message editing;
- WebApp menu button;
- optional custom emoji IDs;
- compatibility fallback for older Bot API servers.

## Interaction model

`/start`, `/menu`, `/deck`, and `/console` open one `COMMAND CONSOLE` message.

Primary modules:

- AI Brief;
- Training;
- World selection;
- VOD Lab;
- Zombies;
- Operator profile;
- Premium;
- System;
- Command Center Mini App.

Every console callback is acknowledged immediately and edits the existing message instead of sending another menu message. This removes callback spinners and prevents chat clutter.

## Dynamic controls

The console reads server-side player state and marks active choices:

- Warzone / BO7 / BF6;
- PC / PlayStation / Xbox;
- Controller / KBM;
- Normal / Pro / Demon;
- Teammate / Coach;
- training focus;
- Zombies map.

Changes are written through `ProfileService`, which keeps canonical `brain_mode` / `voice_mode` synchronized with the legacy `difficulty` / `voice` fields.

## Premium

The inline Premium panel uses the existing server-only entitlement service.

- status comes from Supabase GAME;
- link tokens are generated server-side;
- only token hashes are stored;
- linking does not mint Premium;
- unlink requires an explicit red confirmation screen.

## Legacy compatibility

Older reply-keyboard menus are upgraded at the Telegram transport boundary into inline buttons whose callback data matches the original visible label. Existing deterministic Router handlers continue to work.

Menus requiring contact/location/chat-request capabilities are not converted because those Telegram features have no inline equivalent.

Emergency rollback:

```text
TELEGRAM_AAA_CONSOLE_ENABLED=0
```

This disables the console and inline conversion without changing database state.

## Bot profile surface

At startup the bot configures, on a best-effort basis:

- `/menu`, `/premium`, `/voice`, `/vod`, `/status` commands;
- the default Telegram menu button to open `COMMAND CENTER` when a valid HTTPS WebApp URL exists.

Setup failure does not block FastAPI startup.

## UX constraints

Telegram controls the final button geometry, typography and platform rendering. The bot controls:

- hierarchy;
- color semantics;
- button labels;
- custom emoji IDs when configured;
- navigation structure;
- Rich Message content;
- the fully custom Mini App experience.

BLACK CROWN uses blue/cyan primary actions, green confirmation/progression actions and red destructive/high-risk actions. No gold, fantasy or casino visual language is introduced.

## Validation

Automated coverage includes:

- console opening and legacy keyboard removal;
- inline view composition;
- same-message editing;
- callback acknowledgement;
- private-chat identity boundary;
- dynamic active selections;
- Premium link and unlink flow;
- WebApp menu-button setup;
- legacy keyboard-to-inline conversion;
- emergency rollback;
- rich-message and old Bot API fallback paths;
- profile alias persistence.
