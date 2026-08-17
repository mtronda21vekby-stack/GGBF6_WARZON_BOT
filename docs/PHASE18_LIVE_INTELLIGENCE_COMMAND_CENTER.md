# BLACK CROWN OPS v18 — Live Intelligence Command Center

## Objective

Move BLACK CROWN OPS from a static request/response bot into a live, technical competitive-intelligence product while preserving the working Telegram webhook, persistent Supabase memory, Premium authority, VOD pipeline, voice stack and Mini App security boundary.

The release does not add another paid provider. It reuses the existing OpenAI generation path and changes how partial output is transported and presented.

## Telegram live intelligence

Free-form AI requests now run outside the FastAPI event loop and publish ephemeral draft updates while the model is generating.

Transport preference:

1. `sendRichMessageDraft` for native structured BLACK CROWN cards;
2. `sendMessageDraft` for compatible text drafts;
3. no draft when the Telegram API server does not support either method.

Drafts are presentation-only. The existing persistent final message remains authoritative and is delivered through the established `send_message` path.

The draft session:

- uses a random positive `draft_id`;
- coalesces rapid token events into the latest state;
- throttles Telegram updates;
- shows analysis phases rather than fake progress percentages;
- fails open to the normal final response;
- never writes partial output into player memory.

## Streaming generation

`AIHook` can now request a streaming Chat Completions response and emit accumulated partial text through an optional callback.

The normal non-streaming contract remains available. Intent routing, trusted knowledge selection, currentness gates, anti-repeat recovery, response policy and final length enforcement remain authoritative.

The callback is optional and isolated from generation. A broken UI callback cannot fail the AI request.

## Mini App live transport

The shared Intelligence Core is exposed through:

```text
POST /webapp/api/ask/stream
Content-Type: application/x-ndjson
```

Event types:

- `meta` — request identity, trust state and build;
- `partial` — coalescible accumulated response text;
- `pulse` — liveness and elapsed time;
- `final` — authoritative final response;
- `error` — bounded failure metadata without sensitive content.

The endpoint uses the same Telegram Mini App `initData` validation and server-authoritative profile/history path as `/webapp/api/ask`.

When `initData` is invalid or unavailable, the endpoint runs in untrusted/demo context. Client profile and history are sanitized and cannot mutate trusted player state.

## Cinematic technical interface

The Mini App now layers a v18 presentation runtime over the stable existing application:

- graphite/cyan technical visual system;
- vector/CSS BLACK CROWN core mark;
- cinematic boot synchronization sequence;
- network, identity, core and build telemetry rail;
- live phase and latency display;
- progressively updating tactical response bubble;
- command palette (`Ctrl/Cmd + K` on desktop);
- Telegram haptic feedback;
- online/offline state;
- low-power and reduced-motion mode;
- stable JSON fallback when NDJSON streaming is unavailable.

The visual language intentionally avoids casino, fantasy, gold and decorative premium clichés. Premium is expressed through information density, restrained motion, hierarchy and operational feedback.

## Stable-base migration strategy

Large working modules are retained as compatibility bases:

```text
app/core/router_base.py
app/webapp/webapp_router_base.py
app/webapp/static/app.base.js
```

Small v18 wrappers override only the live intelligence boundaries. This reduces regression risk and keeps deterministic menus, presets and security behavior intact.

## Runtime gates and rollback

Telegram drafts:

```text
TELEGRAM_LIVE_DRAFTS_ENABLED=0
```

Mini App v18 overlay and live stream:

```text
WEBAPP_LIVE_STREAM_ENABLED=0
```

or:

```text
WEBAPP_CINEMATIC_UI_ENABLED=0
```

The browser obtains privacy-safe flags from:

```text
POST /webapp/api/runtime
```

The v18 overlay requires both web flags. Disabling either returns the Mini App to the stable base UI without touching player state or database data.

## Security and privacy

- no token, key or complete Telegram `initData` is logged;
- partial responses are ephemeral and not persisted;
- final memory writes retain the established trusted identity boundary;
- client-supplied profile/history never override verified server state;
- response queues and payload sizes are bounded;
- stream failures return bounded error classes, not stack traces or secrets;
- existing abuse limits remain at the canonical AI boundary;
- no new external service or database is required.

## Validation

Automated coverage includes:

- accumulated OpenAI partial generation;
- callback failure isolation;
- Telegram rich-draft/text-draft fallback;
- draft coalescing and final preview;
- Router live-draft integration and rollback;
- untrusted Mini App streaming;
- trusted server profile/history authority;
- runtime feature gates;
- empty-request rejection;
- cinematic asset contracts;
- JavaScript syntax validation;
- release/readiness contracts;
- existing full regression suite and import smoke.

Release target:

```text
18.0.0 / bco-live-intelligence-v18
```
