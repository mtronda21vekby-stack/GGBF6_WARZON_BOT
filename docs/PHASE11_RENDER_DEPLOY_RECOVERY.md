# BLACK CROWN OPS — Phase 11 Render Deploy Recovery

## Evidence from Phase 10

The production gate ran for the full 10-minute window against:

`https://ggbf6-warzon-bot.onrender.com/health/details`

Observed behavior:

- first request timed out while the service was waking;
- subsequent requests returned HTTP 404 for the full window;
- final body was `{"detail":"Not Found"}`.

This proves the public Render service is reachable, but it is not serving the current BLACK CROWN OPS release that contains `/health/details`.

## Goal

Use Render's service deploy hook from GitHub Actions when one is configured, instead of relying only on implicit auto-deploy behavior.

## Secret

Repository Actions secret name:

`RENDER_DEPLOY_HOOK_URL`

Compatibility fallback:

`RENDER_DEPLOY_HOOK`

The hook value must never be committed to the repository or pasted into application source.

## Workflow behavior

On a push to `main`:

1. application CI passes;
2. `render-deploy` checks whether a deploy-hook secret is available;
3. when available, GitHub Actions sends `POST` to the secret hook URL;
4. the hook URL itself is never echoed;
5. HTTP 200/202 is accepted as a deploy trigger;
6. `production-smoke` then waits for the exact release contract and persistent Supabase readiness;
7. when no hook secret exists, workflow reports `mode=none` and falls back to Render auto-deploy, but the production gate still verifies reality.

## Manual one-time setup if mode=none

If the workflow reports `Render deploy trigger: none`, one external configuration step is required because ChatGPT/GitHub/Supabase connectors cannot mutate Render service settings:

1. Render Dashboard → `GGBF6_WARZON_BOT` → Settings.
2. Find **Deploy Hook** and copy the secret hook URL.
3. GitHub repository → Settings → Secrets and variables → Actions.
4. Create repository secret named exactly `RENDER_DEPLOY_HOOK_URL`.
5. Store the Render hook URL as its value.

Do not paste the deploy hook URL into chat.

## Branch correctness

A Render deploy hook deploys the service's configured linked branch. If the hook is accepted but the production gate continues to serve the old release, verify in Render that the service branch is `main`.

## Security

- no Render API credential is added to source;
- no hook URL is printed by the workflow;
- GitHub Actions receives the hook only through encrypted repository secrets;
- production readiness remains independently verified after the deploy trigger;
- Supabase service-role credentials remain unrelated to this hook and never enter the deploy-trigger request.
