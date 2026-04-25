# Incremental Scanning — Post-Launch Roadmap

**Status**: Design draft (not implemented). Triggered post-launch on demand.
**Owner**: Scanner team
**Related**: [README.md § Roadmap](../README.md#post-launch-v2)

---

## Why this is post-launch, not pre-launch

`cl_scan_all` today re-runs every article on every invocation. With Smart Scan
the AI only reads files matched by Grep (typically 20–50 of a project's
hundreds of files), so a single scan completes in 3–5 minutes. For a
once-a-week compliance check that is acceptable.

The cost matters when:

1. A paid customer treats `cl_scan_all` as a CI step and runs it on every PR,
2. The development inner loop wants per-commit feedback without paying full
   token cost each time, or
3. The free tier scan rate climbs high enough that AI provider cost becomes a
   meaningful line item.

None of those signals exist before launch. Building the optimisation now would
be premature.

## Trigger conditions (any one fires the work)

- ≥ 30 % of paid users run ≥ 3 scans / week for 4 weeks running
- AI inference cost / daily-active-user crosses €1
- A paying customer files a "scan loop is too slow" support ticket
- Scanner P95 wall-clock time on representative repos exceeds 8 minutes

## Design summary

The scan boundary becomes "obligation × file fingerprint" instead of "article".

```
Each obligation's detection_method already lists the file globs / patterns it
inspects. After a scan, persist the SHA-256 of every file that contributed
evidence to that obligation. On the next scan:
  - If git diff (HEAD..last-scan-sha) shows no overlap with the persisted file
    set for an obligation, reuse the prior finding (no AI call).
  - Otherwise, re-run the obligation normally.
```

Persistence lives alongside the existing snapshot ledger so the deterministic
state hash remains the single source of truth.

### Persisted shape (additive — no breaking change)

```jsonc
// .compliancelint/local/articles/art09.json (per-article)
{
  "scan_date": "2026-08-01T10:00:00Z",
  "scan_commit_sha": "abc123…",
  "findings": {
    "ART09-OBL-1": {
      "level": "compliant",
      // … existing fields unchanged …
      "evidence_files": [
        { "path": "src/risk/manager.py", "sha256": "def456…" },
        { "path": "docs/risk-management.md", "sha256": "789abc…" }
      ]
    }
  }
}
```

Existing state files without `evidence_files` continue to work — they fall
through to the full-scan path.

### CLI surface

```
cl_scan(articles="9", changed_only=True)
  └─ if changed_only and prior state exists:
       1. compute git-changed file list
       2. for each obligation in article 9: did any evidence_files overlap?
          - no overlap → reuse prior finding
          - overlap → re-scan that obligation only
       3. emit a per-obligation reuse / rescan trace for the audit log
```

Default remains `changed_only=False` (current behaviour) until two release
cycles validate the optimisation in the wild.

## Migration plan

1. Schema additive change: new `evidence_files` array on findings (writers
   start populating, readers tolerate missing).
2. New `cl_scan_all(changed_only=True)` flag — opt-in, off by default.
3. Telemetry: log reuse-vs-rescan ratio per scan; surface in dashboard
   "Scanner Performance" panel after 2 weeks of data.
4. Flip default to `changed_only=True` once telemetry shows reuse rate ≥ 60 %
   and false-reuse incidents = 0 across a full release cycle.

## What this does NOT change

- Obligation engine logic — same deterministic mapping from
  `compliance_answers` to findings.
- Three Locks / Applicability Lock — same legal validation.
- Dashboard / SaaS API — incremental is invisible to anything outside the
  scanner module.
- File-to-obligation reverse index — already implicit in detection_method;
  this design avoids adding a separate index.

## Open questions

- How aggressive should reuse be when `compliance_answers` change but files
  do not? (Likely re-scan unconditionally — answers drive most of the
  evaluation.)
- Should reuse extend across `git pull` boundaries or only within a single
  developer's branch? (First version: same-branch only.)
- Per-obligation telemetry retention — opt-in or always-on for paid tiers?
