# V2 Phase 4B.3 — verified Apple identity link

The production flow uses the existing Telegram identity as ownership proof because it is already attached to the same canonical account as Website. The Website repository is outside this gate, so no new web login surface or weaker email-based proof was introduced.

Flow:

1. iOS authenticates with Apple through Supabase GAME.
2. Render validates the Supabase JWT and starts a 10-minute, single-use Telegram challenge.
3. The user opens the existing bot in a private chat.
4. Telegram supplies the sender identity to the backend; iOS supplies no Telegram ID and no canonical ID.
5. Supabase atomically verifies the active Telegram and Website identities, checks Apple ownership, inserts the active Apple identity, records an audit event, and consumes the challenge.
6. iOS polls status and retries canonical bootstrap.

The migration is additive. No existing canonical account, Website/Telegram identity, entitlement, Player Brain row, RLS policy, or provider credential is replaced.
