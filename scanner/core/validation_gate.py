"""
Validation Gate — ensures compliance_answers are 100% schema-correct before scanning.

Architecture:
  0. Scope check: _scope must have risk_classification (determines which articles apply)
  1. Coerce: auto-fix common AI format mistakes (fuzzy key match, string→bool, etc.)
  2. Validate: strict schema check — every field must be the right type
  3. Enforce: all APPLICABLE articles must be filled (not just the ones AI chose)
  4. Report: structured errors that tell the AI exactly how to fix

Design principles:
  - _scope determines which articles apply (deterministic, not AI's choice)
  - If it can be auto-fixed, fix it silently (coerce)
  - If it can't, return a precise error (validate)
  - Never let malformed data reach the obligation engine
  - Applicable articles not filled → error (not silent UNABLE_TO_DETERMINE)
"""

import difflib
from typing import Any

from core.context import _BOOL_FIELDS, _LIST_FIELDS


# ── Article scope classification ──
# These MUST match BaseArticleModule._HIGH_RISK_ONLY_ARTICLES in protocol.py.
# Future: read from module metadata to avoid duplication.
# When adding a new regulation, add its scope sets here (e.g. _GDPR_CONTROLLER_ONLY).
_HIGH_RISK_ONLY = frozenset({8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 25, 26, 27, 41, 43, 47, 49, 60, 61, 71, 72, 73, 86})

# GPAI model provider obligations (Art. 51-55)
_GPAI_ONLY = frozenset({51, 52, 53, 54, 55})

# Importer-only articles
_IMPORTER_ONLY = frozenset({23})

# Distributor-only articles
_DISTRIBUTOR_ONLY = frozenset({24})

# Risk classification strings that mean "not high-risk"
# Must match BaseArticleModule._NOT_HIGH_RISK_VALUES in protocol.py
_NOT_HIGH_RISK_VALUES = frozenset({
    "not high-risk", "not_high_risk", "not high risk",
    "no", "not applicable", "n/a", "low-risk", "low risk",
    "minimal risk", "limited risk", "limited-risk",
})


# ── Scope validation ──

_SCOPE_REQUIRED_FIELDS = {
    "risk_classification": "e.g. 'high-risk', 'limited-risk', 'not high-risk'",
    "is_ai_system": "true | false | null",
}


def validate_scope(scope: dict | None) -> list[dict]:
    """Validate _scope has all required fields.

    Returns list of error dicts, empty if valid.
    """
    if not scope or not isinstance(scope, dict):
        return [{
            "field": "_scope",
            "error": "_scope is missing or empty. It is REQUIRED.",
            "fix": "Add _scope to compliance_answers with at least: risk_classification, is_ai_system",
            "template": {k: v for k, v in _SCOPE_REQUIRED_FIELDS.items()},
        }]

    errors = []
    for field_name, hint in _SCOPE_REQUIRED_FIELDS.items():
        val = scope.get(field_name)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            errors.append({
                "field": f"_scope.{field_name}",
                "error": f"_scope.{field_name} is required but missing or empty",
                "fix": f"Set _scope.{field_name} to a value ({hint})",
            })

    return errors


def compute_applicable_articles(scope: dict) -> tuple[set[str], dict[str, str]]:
    """Determine which articles apply based on _scope.

    Returns:
        (applicable_keys, skipped_reasons)
        - applicable_keys: set of article keys like {"art4", "art50", ...}
        - skipped_reasons: {article_key: reason} for non-applicable articles

    Three-state SaaS-list semantics (Phase 2 §B 2026-04-29):
        Key `_applicable_articles_from_saas` controls the path taken:

        ABSENT  → legacy local derivation (v1.1.0 behaviour). Used by
                  scanners running against pre-Phase-2 SaaS deployments
                  AND by offline scans (no SaaS connection). Local
                  filter applies role + risk gates exactly as before.

        None    → SaaS-confirmed "see all 44". Free tier sentinel.
                  Bypasses local filter (no role-based narrowing).
                  Spec §B legal-safety: free users see everything.

        list    → SaaS-supplied authoritative list. Scanner echoes the
                  list verbatim, attributing skipped articles with a
                  "Decided by SaaS Applicability Engine" reason. Local
                  derivation is NOT consulted — IP-protection rule.

        empty list → defensive fallback to "all 44". Per Spec §B never
                  fall back to "scan nothing" — legal risk asymmetry.
    """
    all_article_nums = _all_article_nums()

    # ── Phase 2 §B SaaS-list-wins path ───────────────────────────────
    if "_applicable_articles_from_saas" in scope:
        saas_list = scope.get("_applicable_articles_from_saas")
        # None or [] → fall through to "all 44" (legal-safe sentinel)
        if isinstance(saas_list, list) and len(saas_list) > 0:
            applicable = {str(a) for a in saas_list}
            skipped: dict[str, str] = {}
            for art_num in sorted(all_article_nums):
                art_key = f"art{art_num}"
                if art_key not in applicable:
                    skipped[art_key] = (
                        "Decided by SaaS Applicability Engine "
                        f"(_engine_version={scope.get('_saas_engine_version', 'unknown')})"
                    )
            return applicable, skipped
        # Free-tier null sentinel OR defensive empty — return all 44.
        applicable = {f"art{n}" for n in all_article_nums}
        return applicable, {}

    # ── Legacy v1.1.0 local derivation ───────────────────────────────
    # _saas_settings_active: only filter articles when SaaS-confirmed settings exist.
    # When False (default), AI-provided role/risk values are IGNORED for filtering —
    # all articles are scanned. This prevents AI mistakes from hiding obligations.
    saas_active = scope.get("_saas_settings_active") is True

    risk = (scope.get("risk_classification") or "").lower().strip()
    risk_conf = (scope.get("risk_classification_confidence") or "").lower().strip()
    # Default: if risk_classification is provided but confidence is missing,
    # assume "medium" confidence. This prevents a missing confidence field
    # from silently disabling all high-risk article skipping.
    if risk and not risk_conf:
        risk_conf = "medium"
    is_not_high_risk = risk in _NOT_HIGH_RISK_VALUES and risk_conf in ("high", "medium")
    is_gpai_provider = scope.get("is_gpai_provider") is True
    is_importer = scope.get("is_importer") is True
    is_distributor = scope.get("is_distributor") is True

    applicable = set()
    skipped: dict[str, str] = {}

    for art_num in sorted(all_article_nums):
        art_key = f"art{art_num}"

        # High-risk only articles (only filter when SaaS settings confirm)
        if saas_active and art_num in _HIGH_RISK_ONLY:
            if is_not_high_risk:
                skipped[art_key] = f"Art. {art_num} applies only to high-risk AI systems. Scope: '{risk}'"
                continue

        # GPAI only articles (only filter when SaaS settings confirm)
        if saas_active and art_num in _GPAI_ONLY:
            if not is_gpai_provider:
                skipped[art_key] = f"Art. {art_num} applies only to GPAI model providers"
                continue

        # Importer only (only filter when SaaS settings confirm)
        if saas_active and art_num in _IMPORTER_ONLY:
            if not is_importer:
                skipped[art_key] = f"Art. {art_num} applies only to importers"
                continue

        # Distributor only (only filter when SaaS settings confirm)
        if saas_active and art_num in _DISTRIBUTOR_ONLY:
            if not is_distributor:
                skipped[art_key] = f"Art. {art_num} applies only to distributors"
                continue

        applicable.add(art_key)

    return applicable, skipped


# ── Known article keys (canonical) ──

# Articles with explicit field definitions (bool/list validation applies)
_SCHEMA_ARTICLE_KEYS: set[str] = set(_BOOL_FIELDS.keys()) | set(_LIST_FIELDS.keys())


def _discover_all_article_keys() -> set[str]:
    """Discover all article keys from modules directory.

    Auto-discovers — adding a new regulation's modules directory
    automatically adds its articles to the validation gate.
    No hardcoded article lists.
    """
    import os
    import re
    keys = set(_SCHEMA_ARTICLE_KEYS)
    modules_dir = os.path.join(os.path.dirname(__file__), "..", "modules")
    if os.path.isdir(modules_dir):
        for name in os.listdir(modules_dir):
            m = re.match(r"art(\d+)", name)
            if m:
                # Normalize: strip leading zeros (art04 → art4)
                keys.add(f"art{int(m.group(1))}")
    return keys


# Discovered once at import time (fast — just reads directory names)
_ALL_ARTICLE_KEYS: set[str] = _discover_all_article_keys()

# Backward compat alias
_KNOWN_ARTICLE_KEYS = _ALL_ARTICLE_KEYS


# ── Fuzzy key mapping for common AI mistakes ──

# AI often invents keys like "art50_transparency" or "art_50" instead of "art50"
# This maps common patterns to canonical keys
def _fuzzy_match_article_key(wrong_key: str) -> str | None:
    """Try to match a wrong article key to a canonical one.

    Returns the canonical key if a confident match is found, None otherwise.
    """
    # Normalize: lowercase, strip whitespace
    norm = wrong_key.lower().strip().replace("-", "").replace(" ", "")

    # Direct match after normalization
    if norm in _ALL_ARTICLE_KEYS:
        return norm

    # Extract article number from various formats:
    # "art50_transparency" → "art50"
    # "article_50" → "art50"
    # "art_50" → "art50"
    import re
    m = re.search(r"art(?:icle)?[_\s]*(\d+)", norm)
    if m:
        candidate = f"art{m.group(1)}"
        if candidate in _ALL_ARTICLE_KEYS:
            return candidate

    # Use difflib as last resort (must be >0.6 similarity)
    matches = difflib.get_close_matches(norm, _ALL_ARTICLE_KEYS, n=1, cutoff=0.6)
    if matches:
        return matches[0]

    return None


# ── Coerce layer ──

def coerce_answers(compliance_answers: dict) -> tuple[dict, list[dict]]:
    """Auto-fix common AI format mistakes in compliance_answers.

    Returns:
        (coerced_answers, coerce_log) — the fixed dict and a log of what was changed.
    """
    coerced = {}
    log: list[dict] = []

    for key, value in compliance_answers.items():
        # Skip internal keys
        if key.startswith("_"):
            coerced[key] = value
            continue

        canonical = key if key in _KNOWN_ARTICLE_KEYS else _fuzzy_match_article_key(key)

        if canonical and canonical != key:
            log.append({
                "action": "key_renamed",
                "original": key,
                "corrected": canonical,
                "reason": f"Renamed '{key}' to canonical key '{canonical}'",
            })
            key = canonical

        if canonical is None:
            # Unknown key — keep it (might be ai_model or other metadata), don't block
            coerced[key] = value
            log.append({
                "action": "unknown_key_kept",
                "key": key,
                "reason": f"Unknown article key '{key}' — not in schema, kept as-is",
            })
            continue

        # Value must be a dict for article answers
        if isinstance(value, str):
            # AI put a string description instead of a dict — try to infer
            coerced_value = _coerce_string_to_article_dict(canonical, value)
            if coerced_value is not None:
                coerced[key] = coerced_value
                log.append({
                    "action": "string_to_dict",
                    "key": key,
                    "reason": f"Converted string value to structured dict for '{key}'",
                })
            else:
                coerced[key] = {}
                log.append({
                    "action": "string_replaced_empty",
                    "key": key,
                    "original_preview": value[:100],
                    "reason": f"Could not parse string value for '{key}', replaced with empty dict",
                })
            continue

        if not isinstance(value, dict):
            coerced[key] = {}
            log.append({
                "action": "non_dict_replaced",
                "key": key,
                "received_type": type(value).__name__,
                "reason": f"Expected dict for '{key}', got {type(value).__name__}",
            })
            continue

        # Coerce individual fields within the article dict
        coerced_fields, field_log = _coerce_article_fields(canonical, value)
        coerced[key] = coerced_fields
        log.extend(field_log)

    return coerced, log


def _coerce_string_to_article_dict(article_key: str, value: str) -> dict | None:
    """Try to convert a string value like 'NON_COMPLIANT - no logging found' into a dict.

    AI sometimes puts "NOT_APPLICABLE - reason" instead of structured answers.
    We can infer boolean values from common patterns.
    """
    low = value.lower().strip()

    # "NOT_APPLICABLE" / "N/A" for the whole article → all bools = None
    if low.startswith(("not_applicable", "n/a", "not applicable")):
        result = {}
        for field_name in _BOOL_FIELDS.get(article_key, []):
            result[field_name] = None
        for field_name in _LIST_FIELDS.get(article_key, []):
            result[field_name] = []
        return result

    # "NON_COMPLIANT - ..." → all bools = False (conservative)
    if low.startswith("non_compliant"):
        result = {}
        for field_name in _BOOL_FIELDS.get(article_key, []):
            result[field_name] = False
        for field_name in _LIST_FIELDS.get(article_key, []):
            result[field_name] = []
        return result

    # "COMPLIANT - ..." → all bools = True
    if low.startswith("compliant"):
        result = {}
        for field_name in _BOOL_FIELDS.get(article_key, []):
            result[field_name] = True
        for field_name in _LIST_FIELDS.get(article_key, []):
            result[field_name] = []
        return result

    return None


def _coerce_article_fields(article_key: str, fields: dict) -> tuple[dict, list[dict]]:
    """Coerce individual fields within an article's answers dict.

    Handles: string booleans, int booleans, string lists, nested dicts with wrong field names.
    """
    result = dict(fields)
    log: list[dict] = []

    # Coerce bool fields
    for field_name in _BOOL_FIELDS.get(article_key, []):
        if field_name in result:
            val = result[field_name]
            if isinstance(val, str):
                coerced = _coerce_string_to_bool(val)
                if coerced is not _SENTINEL:
                    if coerced != val:
                        log.append({
                            "action": "bool_coerced",
                            "key": f"{article_key}.{field_name}",
                            "original": val,
                            "corrected": coerced,
                        })
                    result[field_name] = coerced
            elif isinstance(val, int) and not isinstance(val, bool):
                result[field_name] = bool(val)
                log.append({
                    "action": "int_to_bool",
                    "key": f"{article_key}.{field_name}",
                    "original": val,
                    "corrected": bool(val),
                })

    # Coerce list fields
    for field_name in _LIST_FIELDS.get(article_key, []):
        if field_name in result and not isinstance(result[field_name], list):
            val = result[field_name]
            result[field_name] = [val] if val else []
            log.append({
                "action": "to_list",
                "key": f"{article_key}.{field_name}",
                "original_type": type(val).__name__,
            })

    # Fuzzy match field names within the article
    known_fields = set(_BOOL_FIELDS.get(article_key, [])) | set(_LIST_FIELDS.get(article_key, []))
    unknown_fields = set(result.keys()) - known_fields
    for uf in list(unknown_fields):
        matches = difflib.get_close_matches(uf, known_fields, n=1, cutoff=0.7)
        if matches:
            result[matches[0]] = result.pop(uf)
            log.append({
                "action": "field_renamed",
                "key": f"{article_key}.{uf}",
                "corrected": f"{article_key}.{matches[0]}",
                "reason": f"Fuzzy matched '{uf}' to '{matches[0]}'",
            })

    return result, log


# Sentinel for "could not coerce"
_SENTINEL = object()


def _coerce_string_to_bool(val: str) -> Any:
    """Convert a string to bool/None, or return _SENTINEL if not possible."""
    low = val.lower().strip()
    if low in ("true", "yes", "1"):
        return True
    if low in ("false", "no", "0"):
        return False
    if low in ("null", "none", "", "n/a", "not applicable", "unknown"):
        return None

    # Try to infer from common AI patterns:
    # "PARTIAL - disclosure.ts exists but..." → True (something exists)
    # "NON_COMPLIANT - no logging found" → False
    # "NOT_APPLICABLE - not a chatbot" → None
    if low.startswith("not_applicable") or low.startswith("not applicable"):
        return None
    if low.startswith("non_compliant") or low.startswith("non-compliant"):
        return False
    if low.startswith("compliant"):
        return True
    if low.startswith("partial"):
        return True  # Something was found, even if incomplete

    return _SENTINEL


# ── Validate layer ──

class ValidationError:
    """A single validation error for a specific field."""

    def __init__(self, article: str, field: str, expected: str, received: str, fix: str):
        self.article = article
        self.field = field
        self.expected = expected
        self.received = received
        self.fix = fix

    def to_dict(self) -> dict:
        return {
            "article": self.article,
            "field": self.field,
            "expected": self.expected,
            "received": self.received,
            "fix": self.fix,
        }


def validate_answers(compliance_answers: dict) -> tuple[dict[str, list[ValidationError]], dict[str, list[str]]]:
    """Strictly validate compliance_answers after coercion.

    Returns:
        (errors_by_article, missing_fields_by_article)
        - errors_by_article: {article_key: [ValidationError, ...]}
        - missing_fields_by_article: {article_key: [field_name, ...]}
    """
    errors: dict[str, list[ValidationError]] = {}
    missing: dict[str, list[str]] = {}

    for article_key in _ALL_ARTICLE_KEYS:
        if article_key.startswith("_"):
            continue

        art_answers = compliance_answers.get(article_key)

        if art_answers is None:
            continue

        if not isinstance(art_answers, dict):
            errors.setdefault(article_key, []).append(ValidationError(
                article=article_key,
                field="(root)",
                expected="dict",
                received=type(art_answers).__name__,
                fix=f"Value for '{article_key}' must be a JSON object, not {type(art_answers).__name__}",
            ))
            continue

        art_errors, art_missing = _validate_article_fields(article_key, art_answers)
        if art_errors:
            errors[article_key] = art_errors
        if art_missing:
            missing[article_key] = art_missing

    return errors, missing


def _validate_article_fields(article_key: str, fields: dict) -> tuple[list[ValidationError], list[str]]:
    """Validate individual fields within an article's answers."""
    errors: list[ValidationError] = []
    missing_fields: list[str] = []

    # Check bool fields
    for field_name in _BOOL_FIELDS.get(article_key, []):
        if field_name not in fields:
            missing_fields.append(field_name)
            continue
        val = fields[field_name]
        if val is not None and not isinstance(val, bool):
            errors.append(ValidationError(
                article=article_key,
                field=field_name,
                expected="true | false | null",
                received=f"{type(val).__name__}: {str(val)[:80]}",
                fix=f"Set '{article_key}.{field_name}' to true, false, or null (not a string description)",
            ))

    # Check list fields
    for field_name in _LIST_FIELDS.get(article_key, []):
        if field_name not in fields:
            # List fields are optional — empty list is fine
            continue
        val = fields[field_name]
        if not isinstance(val, list):
            errors.append(ValidationError(
                article=article_key,
                field=field_name,
                expected="list (array)",
                received=f"{type(val).__name__}: {str(val)[:80]}",
                fix=f"Set '{article_key}.{field_name}' to an array, e.g. [] or [\"evidence text\"]",
            ))

    return errors, missing_fields


# ── Gate: the main entry point ──

class GateResult:
    """Result of running the validation gate on compliance_answers."""

    def __init__(self):
        self.coerced_answers: dict = {}
        self.coerce_log: list[dict] = []
        self.valid_articles: dict[str, dict] = {}      # article_key → coerced answers
        self.invalid_articles: dict[str, dict] = {}     # article_key → error info
        self.missing_articles: list[str] = []           # applicable articles with no data
        self.skipped_articles: dict[str, str] = {}      # non-applicable → reason
        self.scope_errors: list[dict] = []              # _scope validation errors
        self.applicable_articles: set[str] = set()      # articles that need answers
        self.all_valid: bool = False

    def to_error_response(self) -> dict:
        """Build a structured error response for the AI to self-correct."""
        errors_list = []
        for art_key, info in self.invalid_articles.items():
            errors_list.append({
                "article": art_key,
                "errors": [e.to_dict() for e in info.get("errors", [])],
                "missing_fields": info.get("missing_fields", []),
                "required_schema": _build_article_schema_hint(art_key),
            })

        result = {
            "validation_failed": True,
            "valid_article_count": len(self.valid_articles),
            "invalid_article_count": len(self.invalid_articles),
            "missing_applicable_count": len(self.missing_articles),
            "errors": errors_list,
            "coerce_log": self.coerce_log[:20],
        }

        if self.scope_errors:
            result["scope_errors"] = self.scope_errors
            result["fix_instruction"] = (
                "CRITICAL: _scope is incomplete. Fill _scope.risk_classification "
                "(e.g. 'high-risk', 'limited-risk') and _scope.is_ai_system (true/false). "
                "This determines which articles apply to your project."
            )
        elif self.missing_articles:
            result["missing_applicable_articles"] = sorted(self.missing_articles)
            result["fix_instruction"] = (
                f"You must fill compliance_answers for ALL applicable articles. "
                f"Missing: {', '.join(sorted(self.missing_articles))}. "
                f"For each missing article, fill the boolean fields with true/false/null "
                f"based on your code analysis. Use the compliance_answers_template."
            )
        else:
            result["fix_instruction"] = (
                "Fix the format errors above and re-submit using "
                "cl_scan(article=N, project_context=...). Each boolean field must be "
                "exactly true, false, or null — not a string description."
            )

        return result


def _build_article_schema_hint(article_key: str) -> dict:
    """Build a minimal schema hint for an article to help AI fix errors."""
    hint = {}
    for field_name in _BOOL_FIELDS.get(article_key, []):
        hint[field_name] = "true | false | null"
    for field_name in _LIST_FIELDS.get(article_key, []):
        hint[field_name] = '["evidence text", ...]'
    return hint


def run_gate(compliance_answers: dict) -> GateResult:
    """Run the full validation gate: scope → coerce → validate → enforce.

    Flow:
      1. Validate _scope (must have risk_classification)
      2. Compute applicable articles from _scope
      3. Coerce format errors in compliance_answers
      4. Validate field types
      5. Enforce: all applicable articles must be filled

    Returns a GateResult with valid/invalid/missing articles separated.
    """
    result = GateResult()

    # Step 0: Coerce first (may fix _scope key naming too)
    coerced, coerce_log = coerce_answers(compliance_answers)
    result.coerced_answers = coerced
    result.coerce_log = coerce_log

    # Step 1: Validate _scope
    scope = coerced.get("_scope", {})
    scope_errors = validate_scope(scope)
    result.scope_errors = scope_errors

    if scope_errors:
        # _scope is missing/incomplete — we can't determine which articles apply
        # Still scan what we can, but flag as invalid
        result.all_valid = False
        # Fall back: treat all articles as applicable (conservative)
        applicable = {f"art{n}" for n in _all_article_nums()}
        skipped = {}
    else:
        # Step 2: Compute applicable articles from _scope
        applicable, skipped = compute_applicable_articles(scope)

    result.applicable_articles = applicable
    result.skipped_articles = skipped

    # Step 3: Validate field types
    errors_by_article, missing_by_article = validate_answers(coerced)

    # Step 4: Classify articles
    for article_key in sorted(applicable):
        art_data = coerced.get(article_key)
        art_errors = errors_by_article.get(article_key, [])
        art_missing = missing_by_article.get(article_key, [])

        if art_data is None:
            # Applicable article not filled at all — this is an error
            result.missing_articles.append(article_key)
            result.valid_articles[article_key] = {}
            continue

        if isinstance(art_data, dict) and len(art_data) == 0:
            # Empty dict — OK for articles without schema fields (e.g. art4, art80)
            # but an error for articles WITH schema fields (e.g. art50, art12)
            has_schema = (article_key in _BOOL_FIELDS or article_key in _LIST_FIELDS)
            if has_schema:
                result.missing_articles.append(article_key)
                result.valid_articles[article_key] = {}
                continue
            else:
                # No schema → module handles its own validation
                result.valid_articles[article_key] = art_data
                continue

        if art_errors:
            result.invalid_articles[article_key] = {
                "errors": art_errors,
                "missing_fields": art_missing,
                "original_data": art_data,
            }
        else:
            result.valid_articles[article_key] = art_data

    # Non-applicable articles: mark as skipped (valid, will be NOT_APPLICABLE)
    for art_key, reason in skipped.items():
        result.valid_articles[art_key] = {}  # Empty → scanner's _high_risk_only_check handles

    result.all_valid = (
        len(result.invalid_articles) == 0
        and len(result.missing_articles) == 0
        and len(result.scope_errors) == 0
    )
    return result


def _all_article_nums() -> set[int]:
    """Get all article numbers from _ALL_ARTICLE_KEYS."""
    import re
    nums = set()
    for key in _ALL_ARTICLE_KEYS:
        m = re.match(r"art(\d+)", key)
        if m:
            nums.add(int(m.group(1)))
    return nums
