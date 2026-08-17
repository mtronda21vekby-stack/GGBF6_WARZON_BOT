# v19 operator flow

1. Open Mission Control in Telegram or the Mini App.
2. Review the evidence, objective, protocol and success metric.
3. Accept the current candidate mission.
4. Execute the three phases and in-match rule.
5. Report `clean`, `mixed` or `failed`, with an optional note and bounded metrics.
6. Mission Control records the result and generates the next evidence-backed candidate.

A mission is never silently replaced while active. Refreshing a candidate is read-only; lifecycle mutations require the exact current mission ID.
