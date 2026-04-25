# Human Gates Evidence Verifier — Post-Launch Roadmap

**Status**: Design draft (not implemented). Targets post-launch sprint 1.
**Owner**: Scanner team + dashboard team
**Related**: [README.md § Roadmap](../README.md#post-launch-v2),
            [`feedback_ai_must_verify_evidence`](../private/docs/methodology/) (memory)

---

## Problem

Human Gates questionnaires let users attest that they have met manual
obligations (DPIA, FRIA, oversight assignment, log retention policy, etc.).
Today the evidence path runs:

```
User fills questionnaire → finding_responses.answers → cl_sync → next cl_scan
  promotes finding to COMPLIANT (because evidence_provided overlay).
```

Nothing in that chain checks whether the answer actually satisfies the
underlying legal obligation. A user typing "we did it" in every textarea
reaches 100 % compliance on paper. That is a legal-liability risk: an
auditor reads "COMPLIANT", the trail says "user attested", and the
obligation never required attestation alone.

## Solution: `cl_verify_human_gates` — AI cross-check before promotion

A new MCP tool that, before evidence promotes a finding, runs a separate
LLM pass:

1. Loads the obligation's `source_quote` (verbatim EUR-Lex text)
2. Loads the user's `answers` dict for that finding
3. Asks the LLM: "Does this answer concretely satisfy the requirements
   described in the source_quote? Yes / No / Insufficient."
4. Yes → promote to COMPLIANT
5. Insufficient → flag with specific gap ("source_quote requires X — answer
   does not address X")
6. No → reject, status stays NEEDS_REVIEW with a quality flag

The verifier also runs **cross-obligation consistency** checks: if the user
says in Art. 9 "we performed a DPIA" and in Art. 26(9) "we have not done a
DPIA", the verifier surfaces the contradiction.

## Why post-launch, not pre-launch

- Pre-launch the user base is zero, so there is no answer corpus to verify
  against.
- The verifier is a separate workstream — its absence does not block any
  current functionality, only adds a guardrail on top.
- Building the verifier well requires real user answers as test fixtures.
  Synthetic answers will train an over-cautious or over-permissive verifier.

## Architectural placement

```
                     ┌──────────────────────────────┐
   user fills HG ──► │ finding_responses.answers    │
                     └──────────┬───────────────────┘
                                │
                                ▼
                     ┌──────────────────────────────┐
                     │ cl_sync                      │
                     └──────────┬───────────────────┘
                                │
                                ▼
                     ┌──────────────────────────────┐
                     │ cl_verify_human_gates  (NEW) │ ◄─ runs LLM
                     │   - source_quote vs answer   │     check per
                     │   - cross-obligation diff    │     obligation
                     └──────────┬───────────────────┘
                                │
                       ┌────────┴───────┐
                  PASS │                │ FAIL
                       ▼                ▼
            promote to COMPLIANT   keep NEEDS_REVIEW
            (existing path)        + quality_flag added
```

The verifier is **separate** from `cl_scan` so that:
- Scan-time performance does not regress
- Users can run verifier independently (e.g. a quarterly audit pass)
- Cost is opt-in via the verifier (Pro+ feature)

## Quality bar (the verifier's own tests)

- "I think it's fine" → reject (vague)
- "We have docs somewhere" → reject (non-specific)
- "DPIA template at docs/legal/dpia-2026.md, sections 1–7 cover Art. 35" → accept
- Cross-obligation: Art. 9 "DPIA done", Art. 26(9) "DPIA pending" → flag
- Empty answer → reject (no attempt)
- Answer that addresses a different article → reject

The verifier itself ships with a fixture suite of ≥ 50 known good / known
bad / known ambiguous answers and pinned LLM-version regressions. A change
in the underlying model that flips a known-good to "insufficient" is a
release blocker.

## Output schema

```jsonc
{
  "obligation_id": "ART26-OBL-2",
  "verdict": "insufficient",
  "specific_gap": "Art. 26(2) requires evidence the assigned person has 'necessary competence, training and authority' — answer names the person but does not address training or authority.",
  "confidence": "high",
  "model_used": "claude-opus-4-7",
  "verifier_version": "v1.0.0",
  "verified_at": "2026-09-15T14:00:00Z"
}
```

The verdict + gap surfaces in the dashboard finding card so the user can
revise the answer in place. Audit trail captures the verdict for the
declaration / technical-doc PDFs ("Human Gate verified by ComplianceLint
AI cross-check on 2026-09-15").

## Tier gating

- Free / Starter: not available
- Pro: included, runs on every cl_sync
- Business / Enterprise: included + cross-obligation contradiction detection
  + quarterly audit re-run with model-version comparison

## Open questions

- LLM choice for verifier — same model that scanned? or deliberate cross-vendor
  for independence? (Initial: deliberate cross-vendor — Anthropic for scan,
  OpenAI o3 for verify, mirroring the Three Locks Consensus pattern.)
- Latency budget — synchronous before promotion, or async with delayed
  status? (Initial: synchronous, ≤ 30 s timeout, fail-safe to NEEDS_REVIEW.)
- Should verifier run on cl_update_finding evidence too, not just questionnaire
  responses? (Likely yes — same liability surface.)

## Out of scope (different workstream)

- Real-time monitoring of running AI systems (ComplianceLint scans code +
  docs, never runs AI workloads).
- Automated remediation of failed obligations (`cl_fix` is its own roadmap
  item; the verifier only verifies, it does not fix).
