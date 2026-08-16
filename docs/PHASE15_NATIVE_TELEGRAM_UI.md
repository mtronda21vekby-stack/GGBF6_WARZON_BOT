# BLACK CROWN OPS v15 — Native Telegram UI

## Problem

The v14 command deck improved information architecture but still used the old visual treatment: ordinary app-colored reply-keyboard buttons. On current Telegram clients this looked like a generic utility bot rather than BLACK CROWN OPS.

## Current Telegram capabilities used

The production Bot API now supports:

- native button styles on `KeyboardButton` and `InlineKeyboardButton`:
  - `primary` — blue;
  - `success` — green;
  - `danger` — red;
- optional `icon_custom_emoji_id` on buttons;
- structured Rich Messages through `sendRichMessage`.

No unofficial client or rendered button image is used.

## Button system

The transport layer now enriches all reply and inline keyboards, including older modules that have not yet migrated to the shared builder.

Semantic mapping:

- blue: primary navigation, intelligence, game selection, Command Center;
- green: training, positive/active states, teammate and Premium status;
- red: destructive actions, unlink/reset, Demon and Zombies surfaces;
- neutral: Back, Cancel, Settings and informational rows.

The visible command text remains unchanged, preserving every existing router contract and old cached keyboard action.

## Rich tactical cards

Polished `BLACK CROWN OPS // ...` messages are sent through `sendRichMessage` using safe escaped HTML:

- real native heading;
- native divider;
- paragraphs;
- bullet lists.

User/model text is escaped before insertion and automatic entity detection is disabled.

## Compatibility

The public Telegram API supports the new fields. Two explicit fallbacks protect older self-hosted Bot API deployments:

1. if `sendRichMessage` returns HTTP 400/404, resend as ordinary `sendMessage`;
2. if an old server rejects `style` or `icon_custom_emoji_id`, strip only those fields and retry once.

The fallback does not remove commands or alter routing.

## Optional custom emoji

No proprietary custom emoji ID is committed. Operators can provide an exact label-to-ID map through:

```text
TELEGRAM_BUTTON_CUSTOM_EMOJI_JSON
```

Invalid IDs and malformed JSON are ignored.

## Release

- `APP_VERSION=15.0.0`
- `RELEASE_CONTRACT=bco-aaa-v15`
