# BLACK CROWN OPS — Phase 7 AAA Product Quality

## Mission

Make answer quality measurable and production behavior observable without collecting unnecessary conversation content and without adding another database table/service.

## Quality telemetry

`QualityTelemetry` keeps process-local aggregate counters only:

- request count;
- average intelligence latency;
- provider retry attempts;
- anti-repeat recovery calls;
- currentness blocks;
- empty outputs;
- errors;
- intent distribution;
- knowledge-confidence distribution;
- explicit helpful/not-helpful feedback.

It never stores prompts, user messages, Telegram initData, API keys, bot tokens or response bodies.

`AIHook` exposes generation metadata after each request (`attempts`, `anti_repeat_retry`, `outcome`, `error_class`) so retries are measured rather than guessed.

## Explicit answer feedback

Mini App AI responses receive small `👍 / 👎` controls.

The browser sends only:

- rating: `helpful | not_helpful`;
- SHA-256 fingerprint of the rendered assistant answer;
- surface identifier.

The answer text is not included in the feedback payload.

`/webapp/api/feedback`:

- requires verified Telegram Mini App initData;
- resolves player identity server-side;
- rejects malformed hashes;
- is idempotent per response hash;
- writes an `answer_feedback` progression event through the existing Storage interface;
- requires no new Supabase migration;
- does **not** automatically train or mutate player skill scores.

Feedback becomes an evaluation/product-quality signal, not an uncontrolled self-learning loop.

## Readiness

`GET /health/details` returns privacy-safe runtime readiness:

- AI configured boolean;
- persistent-memory configuration boolean;
- active storage adapter type;
- resilient fallback presence;
- live knowledge/VOD/voice/Mini App/Command Center feature flags;
- aggregate quality telemetry.

It never returns secret values or the Supabase URL.

`/health` remains unchanged for simple liveness probes.

## Offline evaluation

`tests/evals/bco_answer_cases.json` is expanded to representative contracts for:

- casual;
- death analysis;
- positioning;
- movement;
- loadout;
- settings;
- training;
- Zombies;
- VOD text review;
- profile;
- player progress;
- current meta;
- current patch;
- system help.

Current/meta/patch cases explicitly require the freshness guard. VOD/profile/progress cases encode honesty/evidence expectations.

## Runtime cleanup

- FastAPI deprecated `on_event("shutdown")` lifecycle is replaced by lifespan cleanup.
- Pydantic class-based Settings Config is replaced by `SettingsConfigDict`.
- existing Telegram webhook/polling architecture is unchanged.

## Failure policy

Core rule: quality features may fail without taking down the text bot.

- feedback persistence error -> feedback endpoint returns 503; conversation continues;
- telemetry is in-process and lock-protected;
- readiness is observational only;
- no feedback event changes factual currentness or game knowledge;
- no negative rating is converted directly into a player weakness.

## Next hardening candidates

After sufficient real traffic exists:

- analyze feedback rates by intent/knowledge confidence;
- calibrate player skill scores from longitudinal evidence;
- introduce a bounded dead-letter/backfill queue for Supabase outage writes;
- remove proven-dead legacy AI clients after a fresh import/runtime audit;
- establish latency SLOs from production measurements rather than invented targets.
