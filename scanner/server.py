"""
ComplianceLint — EU AI Act Compliance MCP Server

Provides tools for scanning projects against EU AI Act requirements.
Runs locally — code never leaves the developer's machine.

Architecture:
  - Modules are auto-discovered from the modules/ directory
  - Each module implements the ArticleModule protocol (core/protocol.py)
  - server.py provides the MCP interface, modules provide the logic
"""

import importlib.util
import json
import logging
import os
import sys
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

CL_VERSION = "1.1.0"  # ComplianceLint version — displayed in UI, PDF, and scan metadata

logger = logging.getLogger("compliancelint")
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s",
                    stream=sys.stderr)

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.context import analyze_project_metadata, ProjectContext
from core.protocol import BaseArticleModule, ScanResult
from core.config import ProjectConfig
from core.evidence import load_evidence, apply_evidence_to_findings

mcp = FastMCP("compliancelint")

# ── Module Registry ──

_modules: dict[int, BaseArticleModule] = {}


def _discover_modules():
    """Auto-discover all article modules from modules/ directory.

    Lazy strategy: only registers module paths at startup (fast).
    Actual module loading happens on first use via _load_module().
    This keeps server startup under 1 second regardless of module count.
    """
    modules_dir = os.path.join(PROJECT_ROOT, "modules")
    if not os.path.isdir(modules_dir):
        logger.warning("modules/ directory not found")
        return

    count = 0
    for entry in sorted(os.listdir(modules_dir)):
        module_path = os.path.join(modules_dir, entry, "module.py")
        if not os.path.isfile(module_path):
            continue
        _module_paths[entry] = module_path
        count += 1

    logger.info("Server ready — %d modules registered (lazy load)", count)


def _load_module(entry: str) -> None:
    """Load a single module by directory name (lazy, called on first use)."""
    if entry in _module_paths and entry not in _loaded_entries:
        module_path = _module_paths[entry]
        try:
            spec = importlib.util.spec_from_file_location(
                f"cl_modules.{entry}", module_path,
                submodule_search_locations=[os.path.join(PROJECT_ROOT, "modules", entry)],
            )
            mod = importlib.util.module_from_spec(spec)
            mod_dir = os.path.join(PROJECT_ROOT, "modules", entry)
            if mod_dir not in sys.path:
                sys.path.insert(0, mod_dir)
            spec.loader.exec_module(mod)

            if hasattr(mod, "create_module"):
                instance = mod.create_module()
                _modules[instance.article_number] = instance
                _loaded_entries.add(entry)
                logger.info("Loaded Art. %d (%s)", instance.article_number, instance.article_title)
        except Exception as e:
            logger.warning("Failed to load module %s: %s", entry, e)


def _ensure_all_modules_loaded() -> None:
    """Load all registered modules (called by scan-all tools)."""
    for entry in sorted(_module_paths.keys()):
        _load_module(entry)


def _ensure_module_loaded(article_number: int) -> None:
    """Load only the module needed for a specific article scan."""
    # Find the module path that corresponds to this article number
    for entry in _module_paths:
        if f"art{article_number:02d}" in entry or f"art{article_number}-" in entry:
            _load_module(entry)
            return
    # Fallback: load all and let the caller handle missing
    _ensure_all_modules_loaded()


# ── Module registry (populated lazily) ──
_module_paths: dict[str, str] = {}   # entry_name → file path
_loaded_entries: set[str] = set()    # entries already loaded

# Register paths at startup (fast — no imports)
_discover_modules()


def _read_ai_provider(project_path: str) -> str:
    """Read ai_provider from .compliancelint/metadata.json (written by save_metadata)."""
    meta_path = os.path.join(project_path, ".compliancelint", "metadata.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f).get("ai_provider", "")
        except (json.JSONDecodeError, OSError):
            pass
    return ""


# ── MCP Tools ──

@mcp.tool()
def cl_analyze_project(project_path: str) -> str:
    """Analyze a project's structure and sample source code for compliance scanning.

    Returns project metadata (directory tree, manifests, source samples) as a
    STARTING POINT. You MUST then read the full codebase before filling
    compliance_answers. See DEEP SCAN REQUIREMENT below.

    ═══════════════════════════════════════════════════════════════════
    DEEP SCAN REQUIREMENT — READ BEFORE FILLING compliance_answers
    ═══════════════════════════════════════════════════════════════════

    The source_samples in this response are only 5 files × 2KB — a skeleton.
    A compliance verdict based only on these samples is UNRELIABLE and WRONG.

    Before filling any compliance_answers field, you MUST:
      1. Use Grep to SEARCH all source files for relevant patterns
         (see scanning_strategy in the response for per-article guidance)
      2. Read ALL files that match your searches
      3. Read ALL documentation files (README, docs/, *.md)
      4. Read ALL config files (package.json, requirements.txt, CI configs)

    If you cannot read the full codebase (e.g. too many files), set the field
    to null (UNABLE_TO_DETERMINE) — do NOT guess from partial information.

    WHY: This tool's credibility depends on thorough analysis. A compliance
    report based on 5 sample files will be wrong and users will distrust it.
    "I read 3 files and found no logging" is not a compliance verdict.

    ═══════════════════════════════════════════════════════════════════
    AI-FIRST WORKFLOW
    ═══════════════════════════════════════════════════════════════════

    Step 1: Call cl_analyze_project(path)
      -> Get the directory tree and file list
      -> Note which files and directories exist

    Step 2: SMART SCAN THE CODEBASE
      -> Use scanning_strategy from Step 1 response
      -> For each article: Grep for relevant patterns across ALL files
      -> Read the files that match (typically 20-50, not thousands)
      -> Read all documentation (README, docs/)
      -> Read all config files
      -> Report progress to user every ~20 files
      -> Only then fill in compliance_answers

    Step 3: Fill in _scope FIRST, then compliance_answers.

      A. Fill _scope (REQUIRED — determines which articles apply):
         "_scope": {
           "risk_classification": "high-risk" | "limited-risk" | "not high-risk",
           "risk_classification_confidence": "high" | "medium" | "low",
           "is_ai_system": true,
           "territorial_scope_applies": true,
           ... (other _scope fields from template)
         }

      B. Fill compliance_answers for ALL articles in the template.
         The scanner determines which articles are applicable based on _scope.
         Non-applicable articles will be auto-skipped (NOT_APPLICABLE).
         But you MUST fill all articles — the scanner enforces this.

      ╔═══════════════════════════════════════════════════════════════╗
      ║  CRITICAL RULES:                                            ║
      ║                                                             ║
      ║  1. Use template keys EXACTLY: "art50" not "art50_transparency"  ║
      ║  2. Values must be: true, false, or null — NEVER strings    ║
      ║  3. Fill ALL articles in the template, not just relevant ones║
      ║  4. _scope.risk_classification is REQUIRED                  ║
      ╚═══════════════════════════════════════════════════════════════╝

      ╔═══════════════════════════════════════════════════════════════╗
      ║  EVIDENCE QUALITY RULES:                                    ║
      ║                                                             ║
      ║  For every _evidence array, each entry MUST include:        ║
      ║  1. The specific FILE PATH where evidence was found         ║
      ║     e.g. "src/logging.py: structlog configured with JSON"   ║
      ║  2. WHAT was found (not just "found" or "detected")         ║
      ║     e.g. "structlog.configure() with JSONRenderer on L21"   ║
      ║  3. If NOT found: say what was searched and where            ║
      ║     e.g. "Searched all .py/.ts files — no logging imports"  ║
      ║                                                             ║
      ║  NEVER write vague evidence like:                           ║
      ║    ❌ "Logging found"                                       ║
      ║    ❌ "Technical documentation detected"                    ║
      ║    ❌ "No evidence found"                                   ║
      ║  Instead:                                                   ║
      ║    ✅ "src/logging.py:21 — structlog.configure(JSONRenderer)"║
      ║    ✅ "README.md — 18 lines, covers purpose + risk class"   ║
      ║    ✅ "No *.md docs found in docs/ or project root"         ║
      ╚═══════════════════════════════════════════════════════════════╝

      Also include:
        "ai_model": "<REQUIRED — your model ID, e.g. claude-sonnet-4-6>"

    ⚠️  IMPORTANT: Always include "ai_model" in project_context. It is recorded
        in the compliance report as the model that performed the assessment.
        Without it, the report will show "not recorded" in the Assessed By field.

    Step 4: Call cl_scan_all(path, project_context=JSON_WITH_YOUR_ANSWERS)
      -> Scanner maps your answers to legal obligations -> findings with citations
      -> NO regex runs. The scanner trusts your answers completely.

    CONFIDENCE CALIBRATION:
      - "confidence": "high"   → you read the relevant files and are certain
      - "confidence": "medium" → you read the files but some ambiguity remains
      - "confidence": "low"    → you did not read enough files to be certain
      - null                   → you cannot determine this at all

    Args:
        project_path: Absolute path to the project directory.
    """
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    metadata = analyze_project_metadata(project_path)
    return json.dumps(metadata, indent=2, ensure_ascii=False)


# ── Post-Scan Workflow Guidance ──────────────────────────────────────────
#
# Smart, contextual suggestions after scan/fix operations.
# Rules: value-driven (explain WHY), conditional (don't repeat), non-pushy.

def _fetch_saas_scan_settings(config) -> dict | None:
    """Fetch scan settings (roles, riskClassification) from SaaS API.

    Returns None on any error (network, auth, timeout) — scanner silently
    falls back to full 247-obligation scan.
    """
    import urllib.request
    import urllib.error

    if not config.saas_api_key:
        return None

    # We need repo_id — read from .compliancelint/metadata.json
    try:
        import os
        meta_path = os.path.join(config._project_path if hasattr(config, '_project_path') else ".", ".compliancelint", "metadata.json")
        if not os.path.isfile(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        repo_id = meta.get("repo_id")
        if not repo_id:
            return None
    except (OSError, json.JSONDecodeError):
        return None

    url = f"{config.saas_url}/api/v1/repos/{repo_id}/scan-settings"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {config.saas_api_key}",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        logger.debug("SaaS scan-settings fetch failed (silent fallback): %s", e)

    return None


def _build_post_scan_hint(project_path: str, nc_count: int = 0, score_pct: int = -1) -> str:
    """Build contextual post-scan guidance.

    Returns a hint string to append to scan output. Empty string if no hint needed.

    Logic:
      - No API key → suggest cl_connect (one-time discovery)
      - Has API key + auto_sync → already handled, no hint
      - Has API key + manual sync → suggest cl_sync with value reason
        - First time (no previous sync): introduce the feature
        - Score changed or NC items found: recommend tracking progress
    """
    config = ProjectConfig.load(project_path)

    # Auto-sync users: already syncing, no hint needed
    if config.saas_api_key and config.auto_sync:
        return ""

    # No API key: suggest connecting (discovery)
    if not config.saas_api_key:
        return (
            "\n\n--- Compliance Tracking ---\n"
            "Run cl_connect() to create your free dashboard.\n"
            "Then cl_sync() to save results. Your code never leaves your machine.\n"
            "Track compliance progress over time and generate audit-ready PDF reports."
        )

    # Has API key, manual sync mode: suggest sync with value reason
    # Check if they've synced before by looking for sync metadata
    state_dir = os.path.join(project_path, ".compliancelint")
    meta_path = os.path.join(state_dir, "metadata.json")
    has_synced = False
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            has_synced = bool(meta.get("last_sync_at"))
        except (json.JSONDecodeError, OSError):
            pass

    if not has_synced:
        # First time with API key but never synced
        return (
            "\n\n--- Compliance Tracking ---\n"
            "Run cl_sync() to save this scan to your dashboard.\n"
            "Each sync creates a timestamped snapshot — useful for tracking\n"
            "compliance progress and providing audit evidence."
        )

    if nc_count > 0:
        # Has NC items — recommend tracking the fix journey
        return (
            "\n\n--- Compliance Tracking ---\n"
            f"Found {nc_count} non-compliant items. After applying fixes,\n"
            "re-scan and run cl_sync() to record your improvement.\n"
            "Auditors value seeing the compliance progression over time."
        )

    # Fully compliant or no significant change — no hint
    return ""


# ── Unified Multi-Regulation API ──────────────────────────────────────────
#
# These are the canonical tools. The per-article tools below are kept as
# thin wrappers for backward compatibility but will be deprecated.

@mcp.tool()
def cl_scan(
    project_path: str,
    project_context: str = "",
    regulation: str = "eu-ai-act",
    articles: str = "all",
    ai_provider: str = "",
) -> str:
    """Scan a project for compliance with a regulation.

    Unified scanning entry point. Scans one or more articles from a regulation.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: JSON string with AI-enriched project context.
            Call cl_analyze() first, read the codebase, then pass your answers.
        regulation: Which regulation to scan against. Currently supported:
            - "eu-ai-act" (default) — EU AI Act (Regulation (EU) 2024/1689)
            Future: "gdpr", "nist-ai-rmf", etc.
        articles: Which articles to scan. Options:
            - "all" (default) — scan all articles (returns summary)
            - Single number: "12" — scan only Article 12
            - Comma-separated: "9,12,14" — scan multiple articles
            - JSON array: "[9, 12, 14]" — scan multiple articles
        ai_provider: Your FULL AI model identifier including version number
            (e.g. "Anthropic Claude Opus 4.6", "OpenAI GPT-4o", "Google Gemini 2.5 Pro").
            You MUST fill this with your exact model name and version — it is recorded in the
            compliance report for audit traceability. Do NOT abbreviate.
    """
    if regulation != "eu-ai-act":
        return json.dumps({
            "error": f"Regulation '{regulation}' is not yet supported.",
            "fix": "Use regulation='eu-ai-act'.",
            "details": f"Supported: ['eu-ai-act']. Additional regulations are on the roadmap.",
        })

    # Parse project context
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid project_context JSON: {e}"})

        # ── Validation Gate for per-article scan ──
        from core.validation_gate import run_gate
        gate = run_gate(ctx.compliance_answers)
        if gate.coerce_log:
            logger.info("cl_scan — validation gate auto-fixed %d issues", len(gate.coerce_log))
            ctx.compliance_answers = gate.coerced_answers

        # Hard reject on validation failures (same as cl_scan_all)
        if gate.scope_errors:
            return json.dumps({
                "error": "Cannot scan: system classification is missing or incomplete in compliance_answers.",
                "scope_errors": gate.scope_errors,
                "fix": "Fill in risk_classification (e.g., 'high-risk' or 'limited-risk') in the _scope section of compliance_answers.",
            })
        if gate.missing_articles:
            return json.dumps({
                "error": f"Cannot scan: {len(gate.missing_articles)} applicable articles are missing.",
                "missing_articles": sorted(gate.missing_articles),
                "fix": "Fill ALL applicable articles in the compliance_answers_template.",
            })
        if not gate.all_valid:
            return json.dumps({
                "error": f"Cannot scan: {len(gate.invalid_articles)} articles have format errors.",
                "invalid_articles": gate.to_error_response()["errors"],
                "fix": "Fix format errors: boolean fields must be true, false, or null.",
            })

    # Parse articles parameter
    if articles == "all":
        # Delegate to cl_scan_all logic
        return cl_scan_all(project_path, project_context, ai_provider=ai_provider)

    # Parse article numbers
    article_numbers = []
    try:
        # Try JSON array first: [9, 12, 14]
        parsed = json.loads(articles)
        if isinstance(parsed, list):
            article_numbers = [int(a) for a in parsed]
        elif isinstance(parsed, int):
            article_numbers = [parsed]
    except (json.JSONDecodeError, ValueError):
        # Try comma-separated: "9,12,14" or single: "12"
        for part in articles.split(","):
            part = part.strip()
            if part.isdigit():
                article_numbers.append(int(part))

    if not article_numbers:
        return json.dumps({
            "error": f"Invalid articles parameter: '{articles}'",
            "fix": "Use 'all', a single number (e.g. '12'), comma-separated (e.g. '9,12,14'), or JSON array (e.g. '[9,12,14]')",
        })

    # Save AI provider metadata if provided
    if ai_provider:
        from core.state import save_metadata
        save_metadata(project_path, ai_provider=ai_provider)

    # Single article → return full findings + post-scan hint
    if len(article_numbers) == 1:
        output = _scan_single_article(article_numbers[0], project_path, context=ctx, regulation=regulation)
        config = ProjectConfig.load(project_path)
        if config.saas_api_key and config.auto_sync:
            try:
                sync_result = cl_sync(project_path)
                sync_data = json.loads(sync_result)
                if sync_data.get("status") == "synced":
                    output += "\n\n--- Results synced to dashboard ---"
            except Exception as e:
                logger.debug("Auto-sync after scan failed: %s", e)
        else:
            output += _build_post_scan_hint(project_path)
        return output

    # Multiple articles → scan each, persist full results to state,
    # but return compact summaries to stay within MCP response limits.
    results = {}
    for art_num in article_numbers:
        # Full scan + persist to state.json (complete data saved locally)
        result_json = _scan_single_article(art_num, project_path, context=ctx, regulation=regulation)
        # Build compact summary for MCP response
        try:
            result_data = json.loads(result_json)
            findings = result_data.get("findings", [])
            overall = result_data.get("compliance_summary", {}).get("overall", "unknown")

            # Sort findings by severity, take top 5
            _level_order = {"non_compliant": 0, "partial": 1, "unable_to_determine": 2,
                            "not_applicable": 3, "compliant": 4}
            if isinstance(findings, list):
                sorted_f = sorted(findings, key=lambda f: _level_order.get(f.get("level", ""), 5))
                top = [
                    {"obligation_id": f.get("obligation_id", ""),
                     "level": f.get("level", ""),
                     "description": (f.get("description", "") or "")[:200]}
                    for f in sorted_f[:5]
                    if "[COVERAGE GAP" not in (f.get("description", "") or "")
                ]
            else:
                top = []

            results[f"article_{art_num}"] = {
                "overall": overall,
                "finding_count": len(findings) if isinstance(findings, list) else 0,
                "top_findings": top,
                "note": f"Full findings saved to state. Use cl_scan(articles=\"{art_num}\") for details.",
            }
        except json.JSONDecodeError:
            results[f"article_{art_num}"] = {"error": "Failed to parse scan result"}

    output = json.dumps({
        "regulation": regulation,
        "articles_scanned": article_numbers,
        "results": results,
    }, indent=2, default=str)

    # Post-scan: auto-sync or contextual hint
    config = ProjectConfig.load(project_path)
    if config.saas_api_key and config.auto_sync:
        try:
            sync_result = cl_sync(project_path)
            sync_data = json.loads(sync_result)
            if sync_data.get("status") == "synced":
                output += "\n\n--- Results synced to dashboard ---"
        except Exception as e:
            logger.debug("Auto-sync after scan failed: %s", e)
    else:
        output += _build_post_scan_hint(project_path)

    return output


@mcp.tool()
def cl_explain(regulation: str = "eu-ai-act", article: int = 0) -> str:
    """Explain a regulation article in plain language.

    Provides:
    - The official requirement summary
    - What can be automated vs. needs human judgment
    - The ComplianceLint compliance checklist
    - Cross-references to related articles

    Args:
        regulation: Which regulation (default: "eu-ai-act").
        article: Article number to explain (e.g. 12 for Article 12).
    """
    if regulation != "eu-ai-act":
        return json.dumps({"error": f"Regulation '{regulation}' is not yet supported.",
                           "fix": "Use regulation='eu-ai-act'.",
                           "details": "Supported: ['eu-ai-act']. Additional regulations are on the roadmap."})
    _ensure_module_loaded(article)
    if article in _modules:
        explanation = _modules[article].explain()
        return explanation.to_json()
    return json.dumps({
        "error": f"Article {article} explanation not yet available.",
        "fix": f"Available articles: {sorted(_modules.keys())}.",
    })




@mcp.tool()
def cl_scan_all(project_path: str, project_context: str = "", ai_provider: str = "", regulation: str = "eu-ai-act") -> str:
    """Scan a project for ALL available compliance checks in a regulation.

    Returns a SUMMARY report — one row per article with overall status and
    top findings. For detailed findings, use cl_scan(regulation=..., articles="N").

    For best results, call cl_analyze_project() first, then pass your
    understanding as project_context. This enables context-aware scanning
    (e.g., knowing which files are generated, which framework is used).

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
            See cl_analyze_project() output for the recommended workflow.
    """
    import concurrent.futures

    _ARTICLE_TIMEOUT_SECS = 30   # max seconds per article before giving up
    _SUPPORTED_REGULATIONS = {"eu-ai-act"}

    if regulation not in _SUPPORTED_REGULATIONS:
        return json.dumps({
            "error": f"Regulation '{regulation}' is not yet supported.",
            "fix": "Use regulation='eu-ai-act'.",
            "details": f"Supported: {sorted(_SUPPORTED_REGULATIONS)}. Additional regulations are on the roadmap.",
        })

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    # Save AI provider metadata if provided
    if ai_provider:
        from core.state import save_metadata
        save_metadata(project_path, ai_provider=ai_provider)

    # Parse project context — required for scanning
    if not project_context:
        return json.dumps({
            "error": (
                "project_context is required. Call cl_analyze_project() first, "
                "read the output, add your own understanding, then pass the enriched "
                "JSON to cl_scan_all()."
            ),
            "fix": "Call cl_analyze_project() first, then pass its output as project_context.",
        })
    try:
        ctx = ProjectContext.from_json(project_context)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"Invalid project_context JSON: {e}"})

    # ── SaaS Source of Truth: fetch role/risk settings if connected ──
    config = ProjectConfig.load(project_path)
    if config.saas_api_key:
        saas_settings = _fetch_saas_scan_settings(config)
        if saas_settings:
            scope = ctx.compliance_answers.get("_scope", {})
            scope["_saas_settings_active"] = True
            roles = saas_settings.get("roles", [])
            scope["is_importer"] = "importer" in roles
            scope["is_distributor"] = "distributor" in roles
            risk = saas_settings.get("riskClassification")
            if risk:
                scope["risk_classification"] = risk
                scope["risk_classification_confidence"] = "high"
            ctx.compliance_answers["_scope"] = scope
            logger.info("cl_scan_all — SaaS settings applied: roles=%s, risk=%s", roles, risk)

    # ── Validation Gate: coerce + validate compliance_answers ──
    from core.validation_gate import run_gate
    gate = run_gate(ctx.compliance_answers)

    if gate.coerce_log:
        logger.info("cl_scan_all — validation gate auto-fixed %d issues", len(gate.coerce_log))
        # Apply coerced answers back to context
        ctx.compliance_answers = gate.coerced_answers

    if gate.scope_errors:
        # _scope is missing or incomplete — HARD REJECT.
        # Cannot determine which articles apply without risk_classification.
        logger.error("cl_scan_all — _scope validation failed, rejecting scan")
        return json.dumps({
            "error": "Cannot scan: system classification is missing or incomplete in compliance_answers.",
            "scope_errors": gate.scope_errors,
            "fix": (
                "Fill in risk_classification (e.g., 'high-risk' or 'limited-risk') in the "
                "_scope section of compliance_answers. Also set is_ai_system (true/false). "
                "Use the compliance_answers_template from cl_analyze_project()."
            ),
        })

    if gate.missing_articles:
        # Applicable articles not filled — HARD REJECT.
        logger.error("cl_scan_all — %d applicable articles missing: %s",
                      len(gate.missing_articles), gate.missing_articles)
        return json.dumps({
            "error": f"Cannot scan: {len(gate.missing_articles)} applicable articles are missing from compliance_answers.",
            "missing_articles": sorted(gate.missing_articles),
            "fix": (
                "Fill ALL applicable articles in the compliance_answers_template. "
                "Copy the template from cl_analyze_project() response and fill "
                "every boolean field with true, false, or null."
            ),
        })

    if not gate.all_valid:
        # Format errors in articles — HARD REJECT
        logger.error("cl_scan_all — %d articles have format errors: %s",
                     len(gate.invalid_articles), list(gate.invalid_articles.keys()))
        return json.dumps({
            "error": f"Cannot scan: {len(gate.invalid_articles)} articles have format errors in compliance_answers.",
            "invalid_articles": gate.to_error_response()["errors"],
            "fix": (
                "Fix the format errors above and re-submit. Each boolean field must be "
                "exactly true, false, or null — not a string. Use the compliance_answers_template."
            ),
        })

    # Lazy-load all modules now (deferred from startup)
    logger.info("cl_scan_all — loading all modules...")
    _ensure_all_modules_loaded()
    logger.info("cl_scan_all — %d modules loaded, starting scan...", len(_modules))

    # config already loaded above (before SaaS settings fetch)
    BaseArticleModule.set_config(config)
    BaseArticleModule.set_context(ctx)

    # Apply config overrides and generate warnings based on final context values
    _dummy = list(_modules.values())[0] if _modules else None
    ctx_warnings = _dummy._ctx_warnings(_dummy._effective_ctx(project_path)) if _dummy else []

    # Determine which modules to scan
    # 1. Apply explicit skip_articles from config (user override)
    modules_to_scan = {k: v for k, v in _modules.items()
                       if k not in config.skip_articles} if config.skip_articles else dict(_modules)

    # NOTE: High-risk article skipping is handled by BaseArticleModule._skip_if_not_high_risk()
    # in protocol.py. Each module checks ctx.risk_classification during scan().
    # Pass risk_classification in _scope to enable this:
    #   "_scope": { "risk_classification": "not high-risk", "risk_classification_confidence": "high" }

    def _scan_one(art_num: int, mod) -> dict:
        """Run a single article scan and return a compact summary dict."""
        try:
            # Ensure risk_classification from _scope is available on ctx
            # (_scope fields are stored in compliance_answers, not on ctx attributes)
            effective_ctx = mod._effective_ctx(project_path)
            if ctx and not effective_ctx.risk_classification:
                scope = ctx.compliance_answers.get("_scope", {})
                if scope.get("risk_classification"):
                    effective_ctx.risk_classification = scope["risk_classification"]
                    effective_ctx.risk_classification_confidence = scope.get("risk_classification_confidence", "")
                    effective_ctx.risk_reasoning = scope.get("risk_reasoning", "")
            skip_result = mod._high_risk_only_check(effective_ctx, project_path)
            if skip_result is not None:
                result = skip_result
            else:
                result = mod.scan(project_path)
            # Inject AI model attribution
            if ctx and getattr(ctx, "ai_model", ""):
                result.assessed_by = ctx.ai_model

            # Persist to state.json (same as _scan_single_article)
            try:
                from core.state import save_article_result
                state_data = result.to_dict() if hasattr(result, 'to_dict') else {
                    "article_number": art_num,
                    "overall_level": result.overall_level.value if hasattr(result.overall_level, 'value') else str(result.overall_level),
                    "overall_confidence": result.overall_confidence.value if hasattr(result.overall_confidence, 'value') else str(result.overall_confidence),
                    "scan_date": result.scan_date,
                    "findings": {
                        f.obligation_id: {
                            "status": "open",
                            "level": f.level.value if hasattr(f.level, 'value') else str(f.level),
                            "confidence": f.confidence.value if hasattr(f.confidence, 'value') else str(f.confidence),
                            "description": f.description,
                            "remediation": f.remediation,
                            "source_quote": f.source_quote,
                        }
                        for f in result.findings
                    },
                }
                save_article_result(project_path, art_num, state_data)
            except Exception as e:
                logger.warning("Could not save state for Art. %d: %s", art_num, e)

            # Build compact summary — top findings by severity only
            level_order = {"non_compliant": 0, "partial": 1, "unable_to_determine": 2,
                           "not_applicable": 3, "compliant": 4}
            sorted_findings = sorted(
                result.findings,
                key=lambda f: level_order.get(f.level.value if hasattr(f.level, 'value') else str(f.level), 5)
            )
            top_findings = [
                {
                    "obligation_id": f.obligation_id,
                    "level": f.level.value if hasattr(f.level, 'value') else str(f.level),
                    "description": (f.description or "")[:200],
                }
                for f in sorted_findings[:5]
                if "[COVERAGE GAP" not in (f.description or "")
            ]

            return {
                "overall": result.overall_level.value,
                "finding_count": len(result.findings),
                "top_findings": top_findings,
                "assessed_by": result.assessed_by or "",
                "note": f"Use cl_scan(articles=\"{art_num}\") for full findings.",
            }
        except Exception as e:
            logger.error("Art. %d scan ERROR: %s", art_num, e)
            return {"error": str(e), "overall": "unable_to_determine"}

    results = {}
    articles_scanned = []
    overall_levels = []

    # ── Phased execution order ──
    # Phase 1: Art.4 (AI literacy) + Art.5 (prohibitions) — universal, no prerequisites
    # Phase 2: Art.6 (risk classification) — determines Art.9-15+ applicability
    # Phase 3: Art.50 (transparency) + Art.51-55 (GPAI) — no high-risk prerequisite
    # Phase 4: Art.9-15, 17-19, 26, 27, 43, 47, 49, 72, 73, 86 — high-risk obligations
    _PHASE_ORDER = [
        (4, 5),        # Phase 1: universal obligations (all AI systems)
        (6,),          # Phase 2: risk classification
        (50, 51, 52, 53, 54, 55),  # Phase 3: general transparency + GPAI
        (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 41, 43, 47, 49, 60, 61, 71, 72, 73, 80, 82, 86, 91, 92, 111),  # Phase 4: high-risk + authority powers + transitional
    ]

    def _run_article(art_num, mod):
        """Run one article with timeout, return summary."""
        logger.info("Scanning Art. %d...", art_num)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_scan_one, art_num, mod)
            try:
                return future.result(timeout=_ARTICLE_TIMEOUT_SECS)
            except concurrent.futures.TimeoutError:
                logger.error("Art. %d TIMEOUT", art_num)
                return {
                    "error": f"Scan timed out after {_ARTICLE_TIMEOUT_SECS}s.",
                    "fix": f"Use cl_scan(articles=\"{art_num}\") to retry.",
                    "overall": "unable_to_determine",
                }

    for phase in _PHASE_ORDER:
        for art_num in phase:
            if art_num not in modules_to_scan:
                continue
            mod = modules_to_scan[art_num]
            summary = _run_article(art_num, mod)

            key = f"article_{art_num}"
            results[key] = summary
            title = mod.article_title
            status = summary.get("overall", "error")
            articles_scanned.append(f"Art. {art_num} ({title}): {status}")
            overall_levels.append(summary.get("overall", "unable_to_determine"))

            # Note: Art.6 scan checks documentation quality, not risk level.
            # Risk classification comes from AI-provided ctx.risk_classification.
            # _high_risk_only_check() in each module handles gating.

    # Determine worst-case overall
    if "non_compliant" in overall_levels:
        overall = "non_compliant"
    elif "partial" in overall_levels:
        overall = "partial"
    elif all(l == "compliant" for l in overall_levels):
        overall = "compliant"
    else:
        overall = "unable_to_determine"

    report = {
        "report_type": "compliance_scan_summary",
        "project": project_path,
        "overall_compliance": overall,
        "articles_scanned": articles_scanned,
        "total_modules": len(modules_to_scan),
        "regulation": "EU AI Act (Regulation (EU) 2024/1689)",
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "config": {
            "loaded": config.has_config,
            "skip_articles": config.skip_articles,
        } if config.has_config else None,
        "context_warnings": [w.__dict__ for w in ctx_warnings] if ctx_warnings else [],
        "validation_gate": {
            "coerce_fixes": len(gate.coerce_log) if gate.coerce_log else 0,
            "coerce_details": gate.coerce_log[:10] if gate.coerce_log else [],
            "invalid_articles": gate.to_error_response()["errors"] if not gate.all_valid else [],
            "note": (
                "Your compliance_answers had format issues that were auto-corrected. "
                "Next time, use the exact keys and types from compliance_answers_template. "
                "Boolean fields must be true/false/null, not strings."
            ) if gate.coerce_log else None,
        } if gate else {},
        "results": results,
        "next_steps": (
            "IMPORTANT: Do not stop here. Your job is to help the user reach full compliance.\n\n"
            "1. REVIEW the findings above. For each NC or NEEDS_REVIEW article:\n"
            "   - Read the specific files mentioned in the evidence\n"
            "   - Identify exactly what code/docs changes would fix the finding\n"
            "   - Propose a concrete fix plan to the user\n\n"
            "2. ASK the user: 'I found N issues. I can fix the most impactful one first "
            "(Art.X with Y findings). Should I start?'\n\n"
            "3. If user agrees: modify the code, then re-scan to verify the fix worked.\n\n"
            "4. REPEAT until all findings are COMPLIANT or the user decides to stop.\n\n"
            "5. For findings that require human judgment (NEEDS_REVIEW with no code fix), "
            "ask the user to confirm with cl_update_finding.\n\n"
            "6. CHANGES TRACKING (do this after every scan):\n"
            "   Identify the project's version control or change tracking system "
            "(e.g., git, SVN, Mercurial, Perforce, or any other mechanism). "
            "Retrieve the history of changes since the last compliance scan. "
            "Summarize what was modified and why, focusing on changes relevant to "
            "compliance findings. Save the summary to .compliancelint/changes_summary.txt "
            "so that cl_sync can include it in the dashboard upload.\n"
            "   Example: 'Added structured logging (src/logger.py), created risk management "
            "docs (docs/risk-management.md), implemented bias examination (src/fairness.py)'\n\n"
            "Do NOT just display this report and wait. Proactively help the user fix issues."
        ),
        "disclaimer": (
            "AI-assisted compliance assessment, not a legal opinion. "
            "All findings require human review and legal counsel."
        ),
    }

    # If validation gate found errors, prepend fix instructions to next_steps
    if gate and not gate.all_valid:
        invalid_keys = sorted(gate.invalid_articles.keys())
        fix_instruction = (
            f"VALIDATION GATE: {len(invalid_keys)} article(s) had format errors in "
            f"compliance_answers and were scanned with incomplete data: {', '.join(invalid_keys)}.\n"
            f"Fix the errors listed in validation_gate.invalid_articles and re-scan "
            f"ONLY those articles using cl_scan(article=N, project_context=...) with corrected answers.\n"
            f"Each boolean field must be exactly true, false, or null — not a string.\n"
            f"Use the required_schema in each error entry as your template.\n\n"
        )
        report["next_steps"] = fix_instruction + report["next_steps"]

    output = json.dumps(report, indent=2, default=str)

    # ── Post-scan: role configuration hint ──
    scope = gate.coerced_answers.get("_scope", {}) if gate else {}
    if not scope.get("_saas_settings_active"):
        output_lines = [output]
        output_lines.append(
            "\n\n--- Role & Risk Configuration ---\n"
            "This scan checked all 247 obligations across all roles.\n"
            "For accurate scoring, configure your role and risk classification at:\n"
            "  compliancelint.dev/dashboard \u2192 [repo] \u2192 Settings\n\n"
            "With settings configured:\n"
            "  \u2713 Only applicable articles scanned (faster, more accurate)\n"
            "  \u2713 Compliance score reflects your actual obligations\n"
            "  \u2713 Human Gates show only your required actions\n\n"
            "After syncing (cl_sync), review your AI-detected risk classification\n"
            "in Settings to confirm it matches your assessment."
        )
        output = "".join(output_lines)

    # ── Post-scan: auto-sync or contextual hint ──
    nc_total = sum(
        1 for r in results.values() if isinstance(r, dict) and r.get("overall") == "non_compliant"
    )
    if config.saas_api_key and config.auto_sync:
        try:
            sync_result = cl_sync(project_path)
            sync_data = json.loads(sync_result)
            if sync_data.get("status") == "synced":
                output += "\n\n--- Results synced to dashboard ---"
        except Exception as e:
            logger.debug("Auto-sync after scan_all failed: %s", e)
    else:
        output += _build_post_scan_hint(project_path, nc_count=nc_total)

    return output


@mcp.tool()
def cl_action_guide(obligation_id: str) -> str:
    """Get guidance for completing a Human Gate obligation.

    Human Gates are compliance obligations that require human verification —
    they cannot be determined from code scanning alone. This tool returns
    guidance on where to complete the Human Gate questionnaire.

    IMPORTANT: This tool does NOT return questionnaire content or accept answers.
    Human Gates must be completed at the ComplianceLint dashboard.

    Args:
        obligation_id: The obligation ID (e.g., "ART26-OBL-2").
    """
    import re

    # Validate obligation ID format
    if not re.match(r"^ART\d+-OBL-\d+", obligation_id.upper()):
        return json.dumps({
            "error": f"Invalid obligation ID format: {obligation_id}",
            "fix": "Use format like ART26-OBL-2",
        })

    obl_id = obligation_id.upper()

    # Known Human Gate obligations (manual obligations from deployer/importer/distributor)
    HUMAN_GATES = {
        "ART26-OBL-2": "Human Oversight Assignment",
        "ART26-OBL-6": "Log Retention Policy",
        "ART26-OBL-7": "Worker Notification",
        "ART26-OBL-9": "Data Protection Impact Assessment (DPIA)",
        "ART27-OBL-1": "Fundamental Rights Impact Assessment (FRIA)",
    }

    title = HUMAN_GATES.get(obl_id, f"Obligation {obl_id}")
    is_known_gate = obl_id in HUMAN_GATES

    return json.dumps({
        "obligation_id": obl_id,
        "title": title,
        "is_human_gate": is_known_gate,
        "status": "pending",
        "message": (
            "This Human Gate requires structured questionnaire completion. "
            "Complete it at your ComplianceLint dashboard."
            if is_known_gate else
            f"Obligation {obl_id} may require manual verification. "
            "Check your ComplianceLint dashboard for guidance."
        ),
        "dashboard_url": "https://compliancelint.dev/dashboard",
        "note": "Human Gates cannot be completed from the IDE. The dashboard provides guided forms for each obligation.",
    })


@mcp.tool()
def cl_action_plan(project_path: str, regulation: str = "eu-ai-act", article: int = 0) -> str:
    """Generate a human action plan for compliance.

    Scans articles and combines action items into a prioritized plan.
    Items requiring human judgment are marked accordingly.

    Args:
        project_path: Absolute path to the project directory.
        regulation: Which regulation (default: "eu-ai-act").
        article: Specific article number (0 = all articles).
    """
    if regulation != "eu-ai-act":
        return json.dumps({
            "error": f"Regulation '{regulation}' is not yet supported.",
            "fix": "Use regulation='eu-ai-act'.",
            "details": "Additional regulations are on the roadmap.",
        })

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    _ensure_all_modules_loaded()

    # Check if project context is available (needed for scanning)
    if not BaseArticleModule.get_context():
        return json.dumps({
            "error": "No project context available. Run a scan first (cl_scan or cl_scan_all) before generating an action plan.",
            "fix": "Scan your project first (cl_scan or cl_scan_all), then request the action plan.",
        })

    all_actions = []
    articles_covered = []

    target_articles = [article] if article > 0 else sorted(_modules.keys())
    for art_num in target_articles:
        if art_num not in _modules:
            all_actions.append({
                "priority": "LOW",
                "article": f"Art. {art_num}",
                "action": f"Article {art_num} is not available in this version of ComplianceLint.",
                "details": f"Available articles: {sorted(_modules.keys())}",
                "effort": "N/A",
                "action_type": "error",
            })
            continue
        mod = _modules[art_num]
        try:
            scan_result = mod.scan(project_path)
            plan = mod.action_plan(scan_result)
            all_actions.extend(plan.actions)
            articles_covered.append(f"Art. {art_num} ({mod.article_title})")
        except Exception as e:
            all_actions.append({
                "priority": "HIGH",
                "article": f"Art. {art_num}",
                "action": f"Module error: {e}",
                "details": "Could not scan this article. Check module configuration.",
                "effort": "N/A",
                "action_type": "error",
            })

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    action_dicts = []
    for a in all_actions:
        if hasattr(a, "to_dict"):
            action_dicts.append(a.to_dict())
        elif isinstance(a, dict):
            action_dicts.append(a)
    action_dicts.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 4))

    combined_plan = {
        "project": project_path,
        "articles_covered": articles_covered,
        "total_actions": len(action_dicts),
        "critical": sum(1 for a in action_dicts if a.get("priority") == "CRITICAL"),
        "high": sum(1 for a in action_dicts if a.get("priority") == "HIGH"),
        "medium": sum(1 for a in action_dicts if a.get("priority") == "MEDIUM"),
        "low": sum(1 for a in action_dicts if a.get("priority") == "LOW"),
        "actions": action_dicts,
        "disclaimer": (
            "This action plan is based on ComplianceLint compliance checklist and best practices. "
            "Official CEN-CENELEC standards (expected Q4 2026) may modify these requirements."
        ),
    }
    return json.dumps(combined_plan, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
def cl_check_updates() -> str:
    """Check for EU AI Act regulation updates.

    Returns the current status of relevant standards and upcoming deadlines.
    """
    from datetime import date
    days_remaining = (date(2026, 8, 2) - date.today()).days

    return json.dumps({
        "last_checked": date.today().isoformat(),
        "upcoming_deadlines": [
            {
                "date": "2025-02-02",
                "event": "Art. 5 prohibitions + AI literacy (Art. 4) became enforceable",
                "status": "ALREADY_IN_FORCE",
            },
            {
                "date": "2025-08-02",
                "event": "GPAI obligations (Art. 51-56) became enforceable",
                "status": "ALREADY_IN_FORCE",
            },
            {
                "date": "2026-08-02",
                "event": "High-risk AI system requirements (Art. 6-49) become enforceable",
                "days_remaining": days_remaining,
                "status": "APPROACHING",
            },
            {
                "date": "2026-Q4",
                "event": "CEN-CENELEC harmonized standards expected publication",
                "status": "IN_PROGRESS",
            },
            {
                "date": "2027-08-02",
                "event": "Requirements for AI in regulated products (Annex I products)",
                "status": "FUTURE",
            },
        ],
        "standards_status": [
            {
                "standard": "prEN 18286 — AI Quality Management System",
                "status": "Public Enquiry phase",
                "expected": "Q4 2026",
            },
            {
                "standard": "ISO/IEC DIS 24970 — AI System Logging",
                "status": "Draft International Standard",
                "relevance": "Directly relevant to Art. 12 compliance",
            },
        ],
        "modules_loaded": [
            f"Art. {n} ({m.article_title})" for n, m in sorted(_modules.items())
        ],
        "note": "Regulation tracking will be automated in future versions.",
        "scanner_update": _check_latest_version(),
    }, indent=2)


@mcp.tool()
def cl_interim_standard(article_number: int) -> str:  # Tool name kept for backward compat
    """Show the ComplianceLint compliance checklist for a specific article.

    Interim standards fill the gap where official CEN-CENELEC standards
    don't exist yet. They are clearly marked as non-official and will be
    updated when official standards are published.

    Args:
        article_number: The article number (e.g., 12 for Article 12).
    """
    if article_number in _modules:
        standard = _modules[article_number].compliance_checklist()
        if standard:
            return json.dumps(standard, indent=2, ensure_ascii=False)
        return json.dumps({
            "error": f"No compliance checklist file found for Article {article_number}.",
            "fix": "This article's module exists but the checklist is not yet available.",
            "details": "The module exists but its interim-standard.json is missing.",
        })

    return json.dumps({
        "error": f"No module available for Article {article_number}.",
        "fix": f"Available articles: {sorted(_modules.keys())}.",
        "details": "More compliance checklists will be added as articles are decomposed.",
    })


@mcp.tool()
def cl_update_finding(
    project_path: str,
    obligation_id: str,
    action: str,
    evidence_type: str = "",
    evidence_value: str = "",
    justification: str = "",
) -> str:
    """Update a single compliance finding with evidence, rebuttal, or status change.

    ⚠️  If you need to update more than 3 findings, use cl_update_finding_batch instead.
    It accepts article-level evidence (one file covers all findings in an article)
    and requires only one user approval for the entire batch.

    IMPORTANT — AI MUST VERIFY EVIDENCE BEFORE CALLING THIS TOOL:

    Before calling cl_update_finding with action="provide_evidence", you MUST:
    1. READ the finding's description to understand what the obligation requires
    2. READ the evidence the user is providing (file, URL, or text)
    3. EVALUATE whether the evidence ACTUALLY satisfies the legal requirement
    4. Only call this tool if the evidence is SPECIFIC and SUFFICIENT

    REJECT vague evidence like:
    - "I think it's fine" → Ask: "What specifically satisfies Art.X requirement?"
    - "We have docs somewhere" → Ask: "Where exactly? Please provide the file path."
    - "Partially done" → Do NOT attest. Ask what remains to be done.

    ACCEPT specific evidence like:
    - "docs/risk-management.md Section 2 lists 7 identified risks with mitigations"
    - "src/logging.py implements structlog with JSON output, retention 180 days"
    - "Confirmed: system is high-risk under Annex III 5(b), classification accepted"

    This is critical: evidence_provided findings are upgraded to COMPLIANT on next scan.
    Poor evidence → false COMPLIANT → legal liability for the user.

    Actions:
      - provide_evidence: Attach verified evidence to a finding (AI MUST verify first)
      - rebut: Challenge a finding with justification (suppression)
      - acknowledge: Mark a finding as acknowledged (accepted risk)
      - defer: Defer remediation to a later date
      - resolve: Mark as fixed, pending re-scan verification

    Requires a previous scan (state.json must exist). Does NOT trigger a re-scan.

    Attester identity is automatically read from:
      1. .compliancelintrc "attester" field (name/email/role)
      2. Git config (user.name / user.email)
      3. If neither available, the operation is rejected.

    Args:
        project_path: Absolute path to the project directory.
        obligation_id: The obligation to update (e.g. "ART12-OBL-1").
        action: One of: provide_evidence, rebut, acknowledge, defer, resolve.
        evidence_type: Type of evidence: file, url, or text (for provide_evidence).
        evidence_value: The evidence content (file path, URL, or description).
        justification: Reason for rebuttal (for rebut action).
    """
    import re as _re

    # Validate obligation_id format: ART{N}-OBL-{N}, ART{N}-EXC-{N}, ART{N}-CLS-{N}, etc.
    if not obligation_id or not _re.match(r"^ART\d+-[A-Z]+-\w+", obligation_id):
        return json.dumps({
            "error": f"Invalid finding ID format: '{obligation_id}'.",
            "fix": "Check your findings on the ComplianceLint dashboard, or run cl_scan to see obligation IDs.",
            "details": "Expected format: ART{N}-OBL-{N} (e.g. ART12-OBL-1, ART50-OBL-2).",
        })

    # Validate action
    _VALID_ACTIONS = {"provide_evidence", "rebut", "acknowledge", "defer", "resolve"}
    if action not in _VALID_ACTIONS:
        return json.dumps({
            "error": f"Invalid action: '{action}'.",
            "fix": f"Use one of: {sorted(_VALID_ACTIONS)}.",
        })

    # Read attester identity (config > git config > reject)
    from core.config import ProjectConfig
    config = ProjectConfig.load(project_path)
    attester = config.get_attester(project_path)

    if attester is None:
        return json.dumps({
            "error": "Cannot submit evidence without your name and email (for the audit trail).",
            "fix": (
                "Add attester_name and attester_email to .compliancelintrc. "
                "If the user already ran cl_connect(), their email should be in .compliancelintrc. "
                "If not, ask the user: 'What name and email should I use for the compliance audit trail?' "
                "Then write attester_name and attester_email to .compliancelintrc and retry."
            ),
            "example": {
                "attester_name": "User's full name",
                "attester_email": "user@company.com",
                "attester_role": "Developer (optional)",
            },
        })

    from core.state import update_finding
    result = update_finding(
        project_path=project_path,
        obligation_id=obligation_id,
        action=action,
        evidence_type=evidence_type,
        evidence_value=evidence_value,
        justification=justification,
        attester=attester,
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def cl_update_finding_batch(
    project_path: str,
    updates: str,
) -> str:
    """Update multiple compliance findings in one call.

    Use this instead of calling cl_update_finding repeatedly. One approval from
    the user covers the entire batch — no need to approve each finding separately.

    IMPORTANT — same evidence quality rules as cl_update_finding apply:
    AI MUST verify each piece of evidence is specific and sufficient.

    ── Two modes ──

    Mode 1: Per-obligation updates (explicit)
    Each update targets a specific obligation_id:
    [
      {"obligation_id": "ART09-OBL-1", "action": "provide_evidence",
       "evidence_type": "file", "evidence_value": "docs/risk-management.md"},
      {"obligation_id": "ART50-EXC-1", "action": "rebut",
       "justification": "System is not deployed in biometric context"}
    ]

    Mode 2: Article-level evidence (recommended for bulk evidence)
    Use "article" instead of "obligation_id" — one piece of evidence auto-applies
    to ALL open findings in that article:
    [
      {"article": "art9", "action": "provide_evidence",
       "evidence_type": "file", "evidence_value": "docs/risk-management.md"},
      {"article": "art12", "action": "provide_evidence",
       "evidence_type": "file", "evidence_value": "src/logging_middleware.py"}
    ]
    This expands internally: art9 with 11 open findings → 11 updates, all pointing
    to the same evidence file. Much more natural than listing each obligation.

    You can mix both modes in one batch.

    Args:
        project_path: Absolute path to the project directory.
        updates: JSON array of update objects (per-obligation or article-level).

    Returns: JSON with updated count, errors, and per-item details.
    """
    import re as _re

    # Parse updates JSON
    try:
        updates_list = json.loads(updates)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"Invalid updates JSON: {e}"})

    if not isinstance(updates_list, list):
        return json.dumps({"error": "updates must be a JSON array"})

    if len(updates_list) == 0:
        return json.dumps({"error": "updates array is empty"})

    # ── Separate article-level items from obligation-level items ──
    article_items = []
    obligation_items = []
    for upd in updates_list:
        if not isinstance(upd, dict):
            continue
        if upd.get("article") and not upd.get("obligation_id"):
            article_items.append(upd)
        else:
            obligation_items.append(upd)

    # Expand article-level evidence into per-obligation updates
    expanded_from_articles = []
    if article_items:
        from core.state import expand_article_evidence
        expanded_from_articles = expand_article_evidence(project_path, article_items)

    # Validate obligation-level items
    errors = []
    valid_updates = []
    _VALID_ACTIONS = {"provide_evidence", "rebut", "acknowledge", "defer", "resolve"}

    for i, upd in enumerate(obligation_items):
        if not isinstance(upd, dict):
            errors.append({"index": i, "error": "Update must be an object"})
            continue
        obl_id = upd.get("obligation_id", "")
        action = upd.get("action", "")
        if not obl_id or not _re.match(r"^ART\d+-[A-Z]+-\w+", obl_id):
            errors.append({"index": i, "obligation_id": obl_id, "error": "Invalid finding ID format"})
            continue
        if action not in _VALID_ACTIONS:
            errors.append({"index": i, "obligation_id": obl_id, "error": f"Invalid action: {action}"})
            continue
        valid_updates.append(upd)

    # Combine: expanded article-level + validated obligation-level
    valid_updates = expanded_from_articles + valid_updates

    if not valid_updates:
        return json.dumps({"error": "No valid updates in batch", "validation_errors": errors})

    # Resolve attester (once for entire batch)
    from core.config import ProjectConfig
    config = ProjectConfig.load(project_path)
    attester = config.get_attester(project_path)

    if attester is None:
        return json.dumps({
            "error": "Cannot submit evidence without your name and email (for the audit trail).",
            "fix": "Add attester_name and attester_email to .compliancelintrc.",
        })

    # Execute batch update
    from core.state import update_findings_batch
    result = update_findings_batch(
        project_path=project_path,
        updates=valid_updates,
        attester=attester,
    )

    if errors:
        result["validation_errors"] = errors
    if expanded_from_articles:
        result["article_expansion"] = {
            "article_items_received": len(article_items),
            "obligations_expanded": len(expanded_from_articles),
        }

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def cl_verify_evidence(project_path: str) -> str:
    """Load and return compliance evidence declared by the project maintainer.

    Reads compliance-evidence.json from the project root and returns
    structured verification instructions for each evidence item.

    IMPORTANT — AI CLIENT WORKFLOW:
    For each item where requires_ai_verification=true:
      - type="url"  → Use WebFetch to fetch the URL. Evaluate whether the
                      fetched content satisfies the legal obligation described
                      in obligation_id. Check for required disclosures, policy
                      language, or legal requirements specific to that article.
      - type="file" → Use Read tool to read the file. Evaluate legal adequacy.

    For attestation/screenshot items (requires_ai_verification=false):
      Accept as human-declared. Mark as ATTESTED (unverified) in report.
      Note that these cannot be confirmed by automated analysis.

    After verification, synthesize scan findings + evidence into a final report:
      - Finding was NON_COMPLIANT + evidence URL verified → COMPLIANT (verified)
      - Finding was NON_COMPLIANT + evidence URL insufficient → still NON_COMPLIANT
      - Finding was NON_COMPLIANT + attestation only → ATTESTED (human-declared, unverified)

    Args:
        project_path: Absolute path to the project directory.
    """
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    evidence = load_evidence(project_path)

    if evidence.load_error:
        return json.dumps({
            "error": f"Failed to parse compliance-evidence.json: {evidence.load_error}",
            "fix": "Check that compliance-evidence.json is valid JSON with the correct schema.",
            "details": f"File: {evidence.evidence_file}",
        })

    if not evidence.has_evidence:
        return json.dumps({
            "evidence_file": evidence.evidence_file,
            "found": False,
            "fix": (
                "Create a compliance-evidence.json file in your project root to declare "
                "evidence for obligations that cannot be detected from source code alone "
                "(e.g., external Terms of Service, Privacy Policy URLs, configuration screenshots)."
            ),
            "schema_example": {
                "evidence": {
                    "ART13": {
                        "type": "url",
                        "location": "https://yourcompany.com/terms",
                        "description": "Terms of Service including AI system description and limitations",
                        "provided_by": "Legal Team"
                    },
                    "ART50-ai-disclosure": {
                        "type": "url",
                        "location": "https://yourcompany.com/ai-disclosure",
                        "description": "AI interaction disclosure page shown to users on first login"
                    },
                    "ART12-OBL-3": {
                        "type": "attestation",
                        "description": "Log retention set to 12 months in Vercel dashboard. Screenshot at /legal/vercel-logs.png",
                        "provided_by": "DevOps Team"
                    }
                }
            }
        })

    summary = evidence.to_summary_dict()
    summary["found"] = True
    summary["ai_verification_required"] = evidence.needs_ai_verification != []
    summary["verification_instructions"] = (
        "Process each item in 'items' array:\n"
        "1. If requires_ai_verification=true and type='url': fetch the URL, read its content, "
        "evaluate legal adequacy for the stated obligation_id\n"
        "2. If requires_ai_verification=true and type='file': read the file, evaluate adequacy\n"
        "3. If requires_ai_verification=false: accept as attested, note cannot be verified\n"
        "4. Combine with scan findings to produce final compliance report"
    )

    return json.dumps(summary, indent=2, ensure_ascii=False)


# ── Internal helpers ──

def _scan_single_article(article_number: int, project_path: str, context=None, regulation: str = "eu-ai-act") -> str:
    """Scan a project for a specific article's compliance.

    Args:
        article_number: Article number to scan.
        project_path: Absolute path to the project directory.
        context: ProjectContext object (parsed, not JSON string).
        regulation: Which regulation to scan against (default: "eu-ai-act").
    """
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    from core.scanner_log import get_scanner_logger
    slog = get_scanner_logger(project_path)
    slog.info("scan: article %d started (regulation=%s)", article_number, regulation)

    # Lazy-load the module if not yet loaded
    logger.info("Art. %d — loading module...", article_number)
    _ensure_module_loaded(article_number)

    if article_number not in _modules:
        return json.dumps({
            "error": f"Article {article_number} module not available.",
            "fix": f"Available articles: {sorted(_modules.keys())}.",
        })

    logger.info("Art. %d — scanning %s...", article_number, project_path)

    mod = _modules[article_number]

    # Context is required — return clear error immediately rather than letting
    # scan() raise RuntimeError mid-execution (which can corrupt the MCP pipe on Windows)
    if context is None:
        logger.error("Art. %d — no project_context provided", article_number)
        return json.dumps({
            "error": (
                "project_context is required. Call cl_analyze_project() first, "
                "understand the project, then pass your enriched context JSON."
            ),
            "fix": "Call cl_analyze_project() first, then pass its output as project_context.",
            "details": f"Article {article_number} requires project context for scanning.",
        })

    BaseArticleModule.set_context(context)

    try:
        result = mod.scan(project_path)
    except Exception as e:
        logger.error("Art. %d — scan ERROR: %s", article_number, e)
        return json.dumps({"error": str(e), "article": article_number, "type": type(e).__name__})

    # Inject AI model attribution once at the ScanResult level (not per-finding)
    if context and getattr(context, "ai_model", ""):
        result.assessed_by = context.ai_model

    logger.info("Art. %d — scan complete: %s, %d findings", article_number, result.overall_level.value, len(result.findings))

    data = result.to_dict()

    # Apply evidence annotations — evidence may explain non-compliant findings
    evidence = load_evidence(project_path)
    if evidence.has_evidence and "findings" in data:
        data["findings"] = apply_evidence_to_findings(data["findings"], evidence)
        data["evidence_summary"] = {
            "evidence_file_found": True,
            "total_evidence_items": evidence.total_items if hasattr(evidence, "total_items") else len(evidence.items),
            "note": (
                "Evidence annotations added to relevant findings. "
                "Call cl_verify_evidence() for full verification instructions."
            ),
        }

    # Per-article applicable dates (EU AI Act 2024/1689)
    _applicable_from = {
        5: "2025-02-02",   # Prohibited practices — Chapter II
        6: "2026-08-02",   # High-risk classification — Chapter III
        9: "2026-08-02",   # Risk management system
        10: "2026-08-02",  # Data governance
        11: "2026-08-02",  # Technical documentation
        12: "2026-08-02",  # Record-keeping
        13: "2026-08-02",  # Transparency to users
        14: "2026-08-02",  # Human oversight
        15: "2026-08-02",  # Accuracy and robustness
        50: "2025-08-02",  # GPAI transparency obligations
    }

    # Scan metadata — which files Claude actually read (from _scan_metadata in compliance_answers)
    scan_meta = {}
    if context and hasattr(context, "compliance_answers"):
        raw_meta = context.compliance_answers.get("_scan_metadata", {})
        if raw_meta:
            files_read = raw_meta.get("files_read", [])
            total = raw_meta.get("total_project_files")
            notes = raw_meta.get("scan_notes", "")
            scan_meta = {
                "files_read_count": len(files_read) if isinstance(files_read, list) else 0,
                "total_project_files": total,
                "coverage_pct": (
                    round(len(files_read) / total * 100) if isinstance(files_read, list) and total else None
                ),
                "scan_notes": notes,
            }

    data["compliance_summary"] = {
        "article": f"Art. {article_number} ({mod.article_title})",
        "overall": result.overall_level.value,
        "regulation": "EU AI Act (Regulation (EU) 2024/1689)",
        "applicable_from": _applicable_from.get(article_number, "2026-08-02"),
        "compliance_checklist_version": f"CL-IS-ART{article_number:02d}-v0.1",
        "compliance_checklist_note": (
            "ComplianceLint interim standard — operational interpretation of EU AI Act obligations "
            "pending official harmonised standards (expected 2026-08-02)."
        ),
        "assessed_by": result.assessed_by or "not provided — set ai_model in project_context",
        "scan_date": result.scan_date,
        "scan_coverage": scan_meta or {"note": "not reported — add _scan_metadata to compliance_answers for audit trail"},
        "terminology": {
            "COMPLIANT": "Full compliance confirmed by AI assessment. Human legal sign-off still required.",
            "PARTIAL": "AI found supporting evidence. Human verification required before legal sign-off.",
            "NON_COMPLIANT": "AI found no evidence of compliance, or found prohibited patterns. Human review required.",
            "UNABLE_TO_DETERMINE": (
                "AI could not assess this obligation from available project information. "
                "Use ask mode (scan_mode=ask) for guided evidence collection."
            ),
            "NOT_APPLICABLE": "This article does not apply to this system based on risk classification.",
        },
        "disclaimer": (
            "This report is an AI-assisted compliance assessment, not a legal opinion. "
            "All findings require human review and legal counsel before use in regulatory submissions."
        ),
    }

    # Generate evidence_requests for ask mode
    # Only for PROCESS-type non-compliant findings that don't already have evidence
    config = ProjectConfig.load(project_path)
    if config.is_ask_mode:
        evidence_requests = _build_evidence_requests(
            article_number, mod.article_title, data.get("findings", [])
        )
        if evidence_requests:
            data["evidence_requests"] = evidence_requests
            data["ai_instruction"] = (
                "REQUIRED ACTION — scan_mode=ask is active. Multi-round evidence evaluation:\n\n"
                "STEP 1 — ASK (one question at a time):\n"
                "  For each item in evidence_requests, show the user the 'question' field.\n"
                "  Wait for their response before asking the next question.\n\n"
                "STEP 2 — EVALUATE (after user provides evidence):\n"
                "  - If URL: use WebFetch to fetch the content. Evaluate against acceptance_criteria.\n"
                "  - If file: use Read tool to read the file. Evaluate against acceptance_criteria.\n"
                "  - If attestation/description only: accept as ATTESTED (cannot be verified).\n"
                "  Report your evaluation using the evaluation_format structure:\n"
                "    status: COMPLIANT | NON_COMPLIANT | NEEDS_MORE\n"
                "    criteria_met: which obligation atoms are satisfied\n"
                "    criteria_missing: which atoms are still not satisfied\n"
                "    specific_ask: (if NEEDS_MORE) the exact follow-up question\n\n"
                "STEP 3 — FOLLOW UP (if status=NEEDS_MORE):\n"
                "  Ask the user the specific_ask question. Evaluate again. Repeat until\n"
                "  status is COMPLIANT or NON_COMPLIANT (or user says skip).\n\n"
                "STEP 4 — CROSS-DOCUMENT CONSISTENCY:\n"
                "  After all evidence items are evaluated, check for contradictions:\n"
                "  Do all documents describe the same system, data types, and processes?\n"
                "  Flag any inconsistencies (e.g., Doc A says 'voice data', Doc B says 'text only').\n\n"
                "STEP 5 — RECORD:\n"
                "  If user provided URLs/files → suggest adding them to compliance-evidence.json.\n"
                "  If user said 'skip' → mark as skipped in your final report.\n"
                "  Do NOT proceed to the next article until all evidence_requests are resolved.\n\n"
                "To disable this behavior: add {'scan_mode': 'automation'} to .compliancelintrc"
            )

    # ── Persist to state.json ──
    try:
        from core.state import save_article_result
        state_path = save_article_result(project_path, article_number, data)
        if state_path:
            data["state_saved"] = state_path
    except Exception as e:
        import traceback
        logger.warning("Could not save state.json: %s\n%s", e, traceback.format_exc())

    return json.dumps(data, indent=2, default=str)


def _load_obligation_criteria(obligation_id: str) -> list[str]:
    """Load acceptance criteria from obligation JSON for a given obligation ID.

    Returns list of requirement strings from decomposed_atoms.
    These are the exact legal requirements the evidence must satisfy.
    Returns [] if obligation not found (graceful degradation).
    """
    import re
    match = re.match(r'ART(\d+)', obligation_id, re.IGNORECASE)
    if not match:
        return []

    art_num = int(match.group(1))
    obligations_dir = os.path.join(PROJECT_ROOT, "obligations")
    if not os.path.isdir(obligations_dir):
        return []

    for fname in sorted(os.listdir(obligations_dir)):
        # Match art13-... or art13_... etc.
        if re.match(rf'art{art_num:02d}[-_]', fname) or re.match(rf'art{art_num}[-_]', fname):
            fpath = os.path.join(obligations_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for obl in data.get('obligations', []):
                    if obl.get('id') == obligation_id:
                        atoms = obl.get('decomposed_atoms', [])
                        return [
                            f"{a['atom']}: {a.get('requirement', a.get('description', ''))}"
                            for a in atoms
                            if 'atom' in a
                        ]
            except (json.JSONDecodeError, OSError):
                pass

    return []


def _build_evidence_requests(article_number: int, article_title: str,
                              findings: list[dict]) -> list[dict]:
    """Build a list of questions to ask the user about missing process-level evidence.

    Only generates requests for PROCESS-type non-compliant/partial findings
    that don't already have evidence declared.

    Each request includes acceptance_criteria from the obligation JSON so the AI
    knows exactly what to evaluate the evidence against (multi-round evaluation).
    """
    requests = []
    seen_obligations = set()

    for finding in findings:
        level = finding.get("level", "")
        gap_type = finding.get("gap_type", "")
        obligation_id = finding.get("obligation_id", "")
        has_evidence = "evidence" in finding

        # Only ask for PROCESS findings that are non-compliant/partial and lack evidence
        if (gap_type == "process"
                and level in ("non_compliant", "partial", "unable_to_determine")
                and not has_evidence
                and obligation_id not in seen_obligations
                and "[COVERAGE GAP" not in finding.get("description", "")):

            seen_obligations.add(obligation_id)
            description = finding.get("description", "")
            # Strip the PROCESS FINDING disclaimer for cleaner display
            clean_desc = description.split("[PROCESS FINDING:")[0].strip()

            # Load acceptance criteria from obligation JSON
            # These are the exact legal atoms the evidence must satisfy
            criteria = _load_obligation_criteria(obligation_id)

            req = {
                "obligation_id": obligation_id,
                "article": f"Art. {article_number} ({article_title})",
                "gap_found": clean_desc,
                "question": (
                    f"Scanner could not find evidence for {obligation_id} in the codebase.\n"
                    f"Gap found: {clean_desc}\n\n"
                    f"Does this evidence exist outside the codebase?\n"
                    f"Please provide:\n"
                    f"  a) URL (e.g., policy page on company website)\n"
                    f"  b) File path (relative to project root)\n"
                    f"  c) Description (if manual attestation/screenshot)\n"
                    f"  d) Type 'skip' if this item does not apply"
                ),
                "skippable": True,
                # Structured evaluation output format for AI to use after evidence is provided
                "evaluation_format": {
                    "status": "COMPLIANT | NON_COMPLIANT | NEEDS_MORE",
                    "criteria_met": ["list of atom names that the evidence satisfies"],
                    "criteria_missing": ["list of atom names still not satisfied"],
                    "specific_ask": "If NEEDS_MORE: what exact information is still missing?",
                    "evidence_quality": "VERIFIED_URL | VERIFIED_FILE | ATTESTED | INSUFFICIENT",
                },
            }

            if criteria:
                req["acceptance_criteria"] = criteria
                req["evaluation_note"] = (
                    "When evaluating the user's evidence, check it against each criterion above. "
                    "Report back using evaluation_format. "
                    "If status=NEEDS_MORE, ask a follow-up question citing the specific missing criterion."
                )

            requests.append(req)

    return requests


# ── SaaS Dashboard Tools ──


@mcp.tool()
async def cl_connect(project_path: str, email: str = "", switch_account: bool = False) -> str:
    """Connect to ComplianceLint Dashboard.

    Opens your browser to sign in with GitHub or Google. Once signed in,
    your API key is automatically saved for future cl_sync() calls.

    No email required — just run cl_connect() and sign in via browser.

    Args:
        project_path: Absolute path to the project directory.
        email: (Deprecated, optional) If provided, uses legacy email-based connect.
        switch_account: Set to true to switch to a different account.
            Ignores the current saved API key and opens browser for re-authentication.

    Returns: JSON with connection status and API key.
    """
    import asyncio
    import webbrowser
    import subprocess
    import uuid

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    from core.scanner_log import get_scanner_logger
    slog = get_scanner_logger(project_path)

    config = ProjectConfig.load(project_path)
    saas_url = config.saas_url or "https://compliancelint.dev"

    def _run_curl(args_list, timeout=8):
        """Run curl in a subprocess (blocking helper for asyncio.to_thread)."""
        flags = {"capture_output": True, "text": True, "timeout": timeout}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        return subprocess.run(args_list, **flags)

    slog.info("cl_connect: repo_name=%s project_id=%s has_key=%s", config.repo_name, config.project_id, bool(config.saas_api_key))

    slog.info("cl_connect: checking existing key...")
    # If already connected (and not switching), check if key still works
    if config.saas_api_key and not switch_account:
        try:
            check_url = f"{saas_url}/api/v1/auth/check"
            _chk = await asyncio.to_thread(
                _run_curl,
                ["curl", "-s", "--max-time", "5", "-H",
                 f"Authorization: Bearer {config.saas_api_key}", check_url],
            )
            if _chk.returncode == 0 and _chk.stdout.strip():
                check_data = json.loads(_chk.stdout.strip())
                if check_data.get("valid"):
                    return json.dumps({
                        "status": "already_connected",
                        "email": check_data.get("email", ""),
                        "dashboard_url": f"{saas_url}/dashboard",
                        "message": "Already connected. Run cl_sync() to upload scan results.",
                    })
        except Exception:
            pass  # Key invalid or server unreachable, proceed to reconnect

    # ── Device flow ──
    slog.info("cl_connect: starting device flow")
    connect_token = uuid.uuid4().hex
    connect_url = f"{saas_url}/api/v1/auth/connect?token={connect_token}"
    logger.info("Opening browser for authentication: %s", connect_url)

    try:
        webbrowser.open(connect_url)
    except Exception:
        return json.dumps({
            "error": "Could not open browser automatically.",
            "fix": "Run cl_connect() again. If the browser still doesn't open, check your default browser settings.",
        })

    # Poll dashboard every 2 seconds for up to 90 seconds.
    # Uses asyncio.sleep so the MCP event loop stays responsive.
    poll_url = f"{saas_url}/api/v1/auth/connect/poll?token={connect_token}"
    logger.info("Polling %s (token=%s...)", poll_url[:60], connect_token[:8])

    received_key = None
    slog.info("cl_connect: polling started")
    for attempt in range(45):  # 45 × 2s = 90s
        await asyncio.sleep(2)
        try:
            poll_result = await asyncio.to_thread(
                _run_curl, ["curl", "-s", "--max-time", "5", poll_url],
            )
            slog.debug("cl_connect poll %d/45: rc=%d", attempt + 1, poll_result.returncode)
            if poll_result.returncode == 0 and poll_result.stdout.strip():
                poll_data = json.loads(poll_result.stdout.strip())
                if poll_data.get("status") == "complete":
                    received_key = {
                        "api_key": poll_data.get("api_key", ""),
                        "email": poll_data.get("email", ""),
                    }
                    break
                elif poll_data.get("status") == "expired":
                    return json.dumps({
                        "error": "Connect token expired.",
                        "fix": "Run cl_connect() again to start a new authentication flow.",
                    })
        except Exception:
            pass  # Network error, keep polling

    if not received_key:
        return json.dumps({
            "error": "Timed out waiting for authentication.",
            "fix": "Make sure you completed the sign-in in your browser, then run cl_connect() again.",
        })

    # Save API key to .compliancelintrc
    # repo_name/project_id are pre-derived by `npx compliancelint init` (runs in
    # normal terminal, not MCP). We only set a fallback repo_name here.
    # NEVER call derive_git_identity() or git subprocess in MCP context — it hangs.
    slog.info("cl_connect: saving config")
    config.saas_api_key = received_key["api_key"]
    config.saas_url = saas_url
    if not config.repo_name:
        config.repo_name = os.path.basename(os.path.normpath(project_path))
    # Pre-populate attester from OAuth email (so cl_update_finding works
    # without needing npx init or manual config)
    if not config.attester_email and received_key.get("email"):
        config.attester_email = received_key["email"]
        if not config.attester_name:
            # Use email prefix as name placeholder
            config.attester_name = received_key["email"].split("@")[0]
    config_path = config.save(project_path)
    slog.info("cl_connect: config saved to %s", config_path)

    # Auto-add .compliancelintrc to .gitignore
    gitignore_path = os.path.join(project_path, ".gitignore")
    try:
        existing_gitignore = ""
        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as _gi:
                existing_gitignore = _gi.read()
        if ".compliancelintrc" not in existing_gitignore:
            with open(gitignore_path, "a", encoding="utf-8") as _gi:
                if existing_gitignore and not existing_gitignore.endswith("\n"):
                    _gi.write("\n")
                _gi.write("# ComplianceLint credentials (auto-added by cl_connect)\n")
                _gi.write(".compliancelintrc\n")
    except Exception as e:
        logger.debug("Could not update .gitignore: %s", e)

    email_display = received_key["email"] or "your account"

    slog.info("cl_connect: connected as %s", email_display)
    return json.dumps({
        "status": "connected",
        "email": email_display,
        "dashboard_url": f"{saas_url}/dashboard",
        "config_saved": config_path,
        "message": f"Connected as {email_display}. API key saved to .compliancelintrc. "
                   f"Run cl_sync() to upload scan results to your dashboard.",
    })


@mcp.tool()
def cl_sync(project_path: str, regulation: str = "") -> str:
    """Sync scan results to ComplianceLint Dashboard.

    Reads the latest scan state from .compliancelint/state.json and uploads
    it to the dashboard. Requires a prior cl_connect to set up API key.

    Only findings JSON is sent — source code never leaves the machine.

    Args:
        project_path: Absolute path to the project directory.
        regulation: Filter by regulation (empty = sync all).

    Returns: JSON with sync status and dashboard URL.
    """
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    from core.scanner_log import get_scanner_logger
    slog = get_scanner_logger(project_path)
    slog.info("cl_sync: started project_path=%s", project_path)

    # Load config for API key
    slog.info("cl_sync: loading config")
    config = ProjectConfig.load(project_path)
    slog.info(f"STEP 3: config loaded, api_key={config.saas_api_key[:10] if config.saas_api_key else 'NONE'}...")
    if not config.saas_api_key:
        return json.dumps({
            "error": "No API key configured. Run cl_connect() first to link your dashboard account.",
            "fix": "Run cl_connect() — it opens your browser to sign in.",
        })

    saas_url = config.saas_url or "https://compliancelint.dev"

    # Get project identity — reads config cache, never blocks on git in cl_sync
    slog.info("STEP 3b: loading project_id")
    from core.state import load_state
    # config.project_id is populated by cl_connect (cached in .compliancelintrc)
    # If not there, fall back to .compliancelint/project.json (UUID cache)
    # NEVER call derive_git_identity() here — git can hang in MCP context
    project_id = config.project_id or None
    if not project_id:
        pj_file = os.path.join(project_path, ".compliancelint", "project.json")
        if os.path.isfile(pj_file):
            try:
                with open(pj_file, "r", encoding="utf-8") as _f:
                    project_id = json.load(_f).get("project_id", "") or None
            except Exception:
                pass
    slog.info(f"STEP 3c: project_id={project_id}")

    # Load scan state
    slog.info("STEP 4: loading state")
    state = load_state(project_path)
    slog.info(f"STEP 5: state loaded, articles={list(state.get('articles',{}).keys())}")

    if not state.get("articles"):
        return json.dumps({
            "error": "No scan results found. Run a scan first (e.g., cl_scan(articles='9')).",
            "fix": "Scan at least one article before syncing to the dashboard.",
        })

    # Derive repo name: config > directory name
    # NEVER call git subprocess in MCP context — it hangs the event loop.
    # repo_name/project_id are pre-derived by `npx compliancelint init`.
    slog.info("STEP 6: deriving repo name")
    repo_name = config.repo_name
    if not repo_name:
        repo_name = os.path.basename(os.path.normpath(project_path))
    slog.info(f"STEP 6b: repo_name={repo_name}")

    # Load attestation responses from state.json findings history/evidence
    slog.info("STEP 7: loading attestation responses from state")
    response_items = []
    try:
        for _art_key, art_data in state.get("articles", {}).items():
            for obl_id, finding in art_data.get("findings", {}).items():
                # Collect evidence items (provide_evidence actions)
                for ev in finding.get("evidence", []):
                    provided_by = ev.get("provided_by", {})
                    response_items.append({
                        "obligation_id": obl_id,
                        "action": "provide_evidence",
                        "note": ev.get("value", ""),
                        "evidence_type": ev.get("type", "text"),
                        "evidence_value": ev.get("value", ""),
                        "submitted_by_name": provided_by.get("name", "") if isinstance(provided_by, dict) else "",
                        "submitted_by_email": provided_by.get("email", "") if isinstance(provided_by, dict) else "",
                        "submitted_by_role": provided_by.get("role", "") if isinstance(provided_by, dict) else "",
                        "submitted_at": ev.get("date", ""),
                    })
                # Collect other actions from history (rebut, acknowledge, defer, resolve)
                for entry in finding.get("history", []):
                    action = entry.get("action", "")
                    if action in ("rebut", "acknowledge", "defer", "resolve"):
                        by_info = entry.get("by", {})
                        response_items.append({
                            "obligation_id": obl_id,
                            "action": action,
                            "note": entry.get("justification", "") or entry.get("note", ""),
                            "evidence_type": "",
                            "evidence_value": "",
                            "submitted_by_name": by_info.get("name", "") if isinstance(by_info, dict) else str(by_info),
                            "submitted_by_email": by_info.get("email", "") if isinstance(by_info, dict) else "",
                            "submitted_by_role": by_info.get("role", "") if isinstance(by_info, dict) else "",
                            "submitted_at": entry.get("date", ""),
                        })
                # Collect suppression (rebut)
                supp = finding.get("suppression")
                if supp and not any(r["action"] == "rebut" and r["obligation_id"] == obl_id for r in response_items):
                    submitted_by = supp.get("submitted_by", {})
                    response_items.append({
                        "obligation_id": obl_id,
                        "action": "rebut",
                        "note": supp.get("justification", ""),
                        "evidence_type": "",
                        "evidence_value": "",
                        "submitted_by_name": submitted_by.get("name", "") if isinstance(submitted_by, dict) else "",
                        "submitted_by_email": submitted_by.get("email", "") if isinstance(submitted_by, dict) else "",
                        "submitted_by_role": submitted_by.get("role", "") if isinstance(submitted_by, dict) else "",
                        "submitted_at": supp.get("date", ""),
                    })
    except Exception as _e:
        slog.error(f"STEP 7: Failed to parse attestation responses from state: {_e}")
    slog.info(f"STEP 7b: {len(response_items)} attestation responses loaded")

    # changes_summary feature removed (2026-04-16):
    # - Previously auto-generated from `git log` in cl_sync → caused MCP hangs
    # - Assumed every user had git initialized; many don't
    # - Only consumer was PDF "Code Changes" box (also removed)
    # Always pass null — DB column preserved for backward compat.
    changes_summary = None

    # Apply attestation overrides: rebutted → not_applicable, evidenced → compliant
    articles_data = json.loads(json.dumps(state.get("articles", {})))  # deep copy
    for _art_key, art_data in articles_data.items():
        for _obl_id, finding in (art_data.get("findings") or {}).items():
            if isinstance(finding, dict):
                if finding.get("suppression"):
                    finding["level"] = "not_applicable"
                elif finding.get("evidence") and len(finding["evidence"]) > 0:
                    finding["level"] = "compliant"

    # Derive current git HEAD sha for stale-detection anchor (Track 4a).
    # Read-only git call, safe in MCP. None if not a git repo or git missing.
    head_commit_sha = _derive_head_commit_sha(project_path)
    slog.info(f"STEP 7c: HEAD commit sha = {head_commit_sha[:12] if head_commit_sha else 'none'}")

    # Derive project-identity fingerprint (oldest root commit) for v4
    # §1.2/§1.3 force-push / repo-rewrite detection. Dashboard stores this
    # on first sync and compares on subsequent syncs; mismatch surfaces a
    # warning in the response body (no blocking, no auto-update — owner
    # acknowledges via dashboard UI).
    first_commit_sha = _derive_first_commit_sha(project_path)
    slog.info(f"STEP 7d: first commit sha = {first_commit_sha[:12] if first_commit_sha else 'none'}")

    # Build payload matching the API schema
    payload = {
        "project_id": project_id,
        "repo": repo_name,
        "scanned_at": state.get("last_scan", datetime.now(timezone.utc).isoformat()),
        "scanner_version": CL_VERSION,
        "regulation": state.get("regulation", "eu-ai-act"),
        "ai_provider": _read_ai_provider(project_path),
        "changes_summary": changes_summary or None,
        "articles": articles_data,
        "responses": response_items,  # Finding responses / attestations from state.json
        "commit_sha": head_commit_sha,  # v4 Track 4a: stale-detection anchor per-finding + snapshot ledger
        "first_commit_sha": first_commit_sha,  # v4 §1.2/§1.3: project-identity fingerprint
    }

    # POST to dashboard
    scans_url = f"{saas_url}/api/v1/scans"
    # ensure_ascii=True: prevent mojibake (â€") when Alpine Docker decodes UTF-8 bytes
    data = json.dumps(payload, default=str, ensure_ascii=True).encode("utf-8")
    slog.info(f"STEP 8: about to POST {len(data)} bytes to {scans_url}")

    resp_data = {}

    try:
        slog.info("STEP 9: sending HTTP request via subprocess...")
        import subprocess as _sp
        import tempfile as _tf

        # Write payload to temp file to avoid command-line length limits
        with _tf.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as _tmp:
            _tmp.write(data)
            _tmp_path = _tmp.name

        curl_cmd = [
            "curl", "-s", "-S", "--max-time", "15",
            "-X", "POST", scans_url,
            "-H", "Content-Type: application/json; charset=utf-8",
            "-H", f"Authorization: Bearer {config.saas_api_key}",
            "-d", f"@{_tmp_path}",
            "-w", "\n%{http_code}",
        ]
        _curl_flags = {}
        if hasattr(_sp, "CREATE_NO_WINDOW"):
            _curl_flags["creationflags"] = _sp.CREATE_NO_WINDOW
        result = _sp.run(curl_cmd, capture_output=True, text=True, timeout=20, **_curl_flags)

        # Clean up temp file
        try:
            os.unlink(_tmp_path)
        except Exception:
            pass

        # Parse response: body + http_code on last line
        lines = result.stdout.strip().rsplit("\n", 1)
        body_str = lines[0] if len(lines) > 1 else ""
        http_code = int(lines[-1]) if lines[-1].isdigit() else 0

        slog.info(f"STEP 10: HTTP done, code={http_code}, body={body_str[:200]}")

        if http_code == 401:
            return json.dumps({
                "error": "API key is invalid or expired.",
                "fix": "Run cl_connect() again to generate a new API key.",
            })
        if http_code == 403:
            detail = ""
            upgrade_url = ""
            try:
                resp_json = json.loads(body_str)
                detail = resp_json.get("error", body_str)
                upgrade_url = resp_json.get("upgrade_url", "")
            except Exception:
                detail = body_str
            settings_url = f"{saas_url}/dashboard/settings"
            return json.dumps({
                "error": f"Dashboard returned HTTP 403: {detail}",
                "fix": f"Upgrade your plan at {settings_url}",
            })
        if http_code >= 400:
            return json.dumps({
                "error": f"Dashboard returned HTTP {http_code}.",
                "fix": "Check the dashboard status at compliancelint.dev or try again later.",
                "details": body_str[:500],
            })
        if body_str:
            resp_data = json.loads(body_str)

    except _sp.TimeoutExpired:
        return json.dumps({
            "error": f"Request to {saas_url} timed out after 15 seconds.",
            "fix": "Check your internet connection or try again.",
        })
    except Exception as e:
        slog.info(f"STEP 10-ERR: {e}")
        return json.dumps({"error": f"Sync failed: {e}", "fix": "Check your internet connection or try again."})

    dashboard_url = resp_data.get("dashboard_url", f"{saas_url}/dashboard")
    scan_id = resp_data.get("scan_id", "")

    # v4 §1.2/§1.3 — fingerprint mismatch warning piggy-backs on scan response.
    # Captured raw here; formatted with resolved_repo_id once the pending-
    # evidence block has resolved it (acknowledge URL needs repo_id).
    fingerprint_warnings_raw = (
        resp_data.get("warnings") if isinstance(resp_data, dict) else None
    )
    if fingerprint_warnings_raw:
        slog.info(
            f"STEP 10b: scan response carried {len(fingerprint_warnings_raw)} "
            f"warning(s); will surface after repo_id resolution"
        )

    # ── Evidence v4 deferred-path pull (sub-3b) ──
    # After scan state is uploaded, fetch any pending evidence bytes the
    # team has uploaded via the dashboard and write them to the working
    # tree for the human to git-commit. MCP never runs git writes itself.
    #
    # repo_id resolution: cache → list → match-by-name. Cache lives in
    # .compliancelint/metadata.json under key `repo_id`. On 404 from the
    # pending-evidence list endpoint, cache is invalidated and we retry
    # once with a fresh list+match.
    pending_summary: dict = {}
    human_prompt: str = ""
    resolved_repo_id: str = ""
    slog.info("STEP 11a: resolving SaaS repo_id for pending evidence pull")
    try:
        pending_summary, human_prompt, resolved_repo_id = _run_pending_evidence_pull(
            project_path=project_path,
            saas_url=saas_url,
            api_key=config.saas_api_key,
            repo_name=repo_name,
            slog=slog,
        )
        slog.info(
            "STEP 11b: pending pull done "
            f"repo_id={resolved_repo_id or 'unresolved'} "
            f"pulled={pending_summary.get('pulled', 0)} "
            f"confirmed={pending_summary.get('confirmed', 0)} "
            f"conflicts={pending_summary.get('conflicts', 0)} "
            f"errors={pending_summary.get('errors', 0)}"
        )
    except Exception as e:
        slog.error(f"STEP 11-ERR: pending evidence pull failed: {e}")
        pending_summary = {"error": f"pending evidence pull failed: {e}"}

    # ── Evidence v4 Track 4c-2: broken_link health sweep ──
    # Only runs when we successfully resolved a repo_id in the block above —
    # no repo_id means we can't hit the evidence-health endpoint anyway.
    # Uses the same HEAD commit sha we already derived earlier in this
    # function for the scan_commit_sha anchor (Track 4a).
    broken_link_summary: dict = {}
    if resolved_repo_id:
        slog.info("STEP 11c: running broken_link health sweep for git_path evidence")
        try:
            broken_link_summary = _run_broken_link_check(
                project_path=project_path,
                saas_url=saas_url,
                api_key=config.saas_api_key,
                repo_id=resolved_repo_id,
                checked_at_sha=head_commit_sha,
                slog=slog,
            )
            slog.info(
                "STEP 11d: broken_link sweep done "
                f"checked={broken_link_summary.get('checked', 0)} "
                f"broken={broken_link_summary.get('broken', 0)} "
                f"transitioned={broken_link_summary.get('transitioned', 0)}"
            )
        except Exception as e:
            slog.error(f"STEP 11d-ERR: broken_link sweep failed: {e}")
            broken_link_summary = {"error": f"broken_link sweep failed: {e}"}

    # Format the fingerprint warning now that resolved_repo_id is known.
    # If repo_id is missing (pending-evidence resolution failed), fall back
    # to the dashboard root — user still gets the signal, just a generic URL.
    fingerprint_msg = _format_fingerprint_warning(
        fingerprint_warnings_raw, saas_url, resolved_repo_id or "",
    )
    if fingerprint_msg:
        slog.info("STEP 11e: fingerprint_changed warning surfaced to user")

    result_payload = {
        "status": "synced",
        "scan_id": scan_id,
        "repo_id": resolved_repo_id,
        "dashboard_url": dashboard_url,
        "articles_synced": list(state.get("articles", {}).keys()),
        "message": f"Scan results uploaded. View at: {dashboard_url}",
    }
    if pending_summary:
        result_payload["pending_evidence"] = pending_summary
    if broken_link_summary:
        result_payload["broken_link_check"] = broken_link_summary
    if fingerprint_msg:
        result_payload["fingerprint_warning"] = fingerprint_msg
        result_payload["message"] = (
            f"{result_payload['message']}\n\n{fingerprint_msg}"
        )
    if human_prompt:
        # Surface the prompt at top-level so MCP clients (Claude Code,
        # Cursor) can show it without drilling into nested objects.
        result_payload["action_required"] = human_prompt
        # And append to the human-readable message for one-line UIs.
        result_payload["message"] = (
            f"{result_payload['message']}\n\n{human_prompt}"
        )

    result = json.dumps(result_payload)
    slog.info(f"STEP 11: returning result ({len(result)} bytes)")
    return result


def _derive_head_commit_sha(project_path: str) -> str | None:
    """Return current git HEAD SHA (40-char lowercase hex), or None.

    Used as the stale-detection anchor (Track 4a). Safe in MCP: timeout=2,
    GIT_TERMINAL_PROMPT=0, CREATE_NO_WINDOW. Returns None on any error so
    cl_sync still proceeds when the project isn't a git repo.
    """
    import subprocess
    try:
        flags = {
            "capture_output": True,
            "text": True,
            "cwd": project_path,
            "timeout": 2,
            "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(["git", "rev-parse", "HEAD"], **flags)
        if r.returncode != 0:
            return None
        sha = r.stdout.strip()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _derive_first_commit_sha(project_path: str) -> str | None:
    """Return the oldest root commit SHA (40-char lowercase hex), or None.

    Used as the project-identity fingerprint (v4 §1.2/§1.3). `git rev-list
    --max-parents=0 HEAD` lists root commits; for the single-root case
    (typical), that's one line. For multi-root repos (grafted, unrelated
    histories merged), we take the first line for determinism — any stable
    selector works since the dashboard compares reported-vs-stored, not
    across scanners.
    """
    import subprocess
    try:
        flags = {
            "capture_output": True,
            "text": True,
            "cwd": project_path,
            "timeout": 2,
            "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"], **flags,
        )
        if r.returncode != 0:
            return None
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        if not lines:
            return None
        sha = lines[0].strip()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _format_fingerprint_warning(
    warnings: list | None, saas_url: str, repo_id: str,
) -> str | None:
    """Build a user-facing message from a fingerprint_changed warning in the
    POST /scans response, or None if no such warning is present.

    Returns None for empty list, non-list input, or no matching type. Owner
    acknowledges via dashboard UI — this message just surfaces the signal
    into cl_sync output so the user sees it even when they don't check the
    dashboard immediately.
    """
    if not isinstance(warnings, list):
        return None
    for w in warnings:
        if not isinstance(w, dict) or w.get("type") != "fingerprint_changed":
            continue
        prev = str(w.get("previous_first_commit_sha") or "")
        curr = str(w.get("current_first_commit_sha") or "")
        note = str(w.get("note") or "Repo fingerprint changed")
        ack_url = f"{saas_url.rstrip('/')}/dashboard/repos/{repo_id}"
        return (
            "Fingerprint changed\n"
            f"  Previous: {prev[:12]}...\n"
            f"  Current:  {curr[:12]}...\n"
            f"  {note}\n"
            f"  Owner can acknowledge at: {ack_url}"
        )
    return None


def _curl_json(method: str, url: str, api_key: str, *, body: bytes | None = None,
               timeout: int = 20) -> tuple[int, str]:
    """Invoke curl via subprocess (same pattern as cl_sync POST /scans).

    Returns (http_code, body_string). Raises subprocess errors to caller.
    Matches existing cl_sync HTTP style — no new dependencies.
    """
    import subprocess as _sp
    import tempfile as _tf

    cmd: list[str] = [
        "curl", "-s", "-S", "--max-time", str(timeout),
        "-X", method, url,
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Accept: application/json",
        "-w", "\n%{http_code}",
    ]
    tmp_path: str | None = None
    if body is not None:
        cmd += ["-H", "Content-Type: application/json; charset=utf-8"]
        with _tf.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        cmd += ["-d", f"@{tmp_path}"]

    curl_flags: dict = {}
    if hasattr(_sp, "CREATE_NO_WINDOW"):
        curl_flags["creationflags"] = _sp.CREATE_NO_WINDOW

    try:
        r = _sp.run(cmd, capture_output=True, text=True, timeout=timeout + 5, **curl_flags)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    stdout = r.stdout or ""
    lines = stdout.rsplit("\n", 1)
    body_str = lines[0] if len(lines) > 1 else ""
    code = int(lines[-1]) if lines[-1].isdigit() else 0
    return code, body_str


def _resolve_saas_repo_id(project_path: str, saas_url: str, api_key: str,
                           repo_name: str, slog,
                           force_refresh: bool = False) -> tuple[str, str, str]:
    """Resolve SaaS repo_id: cache → list /api/v1/repos → match by repo_name.

    Returns (repo_id, source, error_reason):
      - ("uuid...", "cache", "")       — read from metadata.json
      - ("uuid...", "list", "")        — resolved by listing + matching name;
                                         cache refreshed as side-effect
      - ("", "", "list_repos_http_NNN") — /repos call failed at transport
      - ("", "", "no_matching_repo")   — name not present in SaaS repos list;
                                         user-facing skip reason
      - ("", "", "list_repos_invalid_json") — malformed response
    """
    from core.pending_evidence import read_cached_repo_id, write_cached_repo_id

    if not force_refresh:
        cached = read_cached_repo_id(project_path)
        if cached:
            slog.info(f"resolve_repo_id: cache hit ({cached})")
            return cached, "cache", ""

    slog.info(f"resolve_repo_id: listing /api/v1/repos (repo_name={repo_name})")
    list_url = f"{saas_url.rstrip('/')}/api/v1/repos"
    try:
        code, body = _curl_json("GET", list_url, api_key, timeout=10)
    except Exception as e:
        slog.error(f"resolve_repo_id: curl failed: {e}")
        return "", "", "list_repos_network_error"

    if code != 200:
        slog.error(f"resolve_repo_id: list /repos HTTP {code}")
        return "", "", f"list_repos_http_{code}"

    try:
        repos_list = json.loads(body) if body else []
    except json.JSONDecodeError as e:
        slog.error(f"resolve_repo_id: invalid JSON from /repos: {e}")
        return "", "", "list_repos_invalid_json"

    if not isinstance(repos_list, list):
        return "", "", "list_repos_invalid_json"

    matched = [r for r in repos_list if isinstance(r, dict) and r.get("name") == repo_name]
    if not matched:
        slog.warning(f"resolve_repo_id: no match for repo_name='{repo_name}' "
                     f"in {len(repos_list)} SaaS repos")
        return "", "", "no_matching_repo"

    repo_id = matched[0].get("id", "")
    if not repo_id:
        return "", "", "list_repos_invalid_json"

    # Cache for next invocation. Failure is non-fatal — next sync just
    # pays one extra HTTP roundtrip.
    try:
        write_cached_repo_id(project_path, repo_id)
        slog.info(f"resolve_repo_id: cached {repo_id} in metadata.json")
    except Exception as e:
        slog.warning(f"resolve_repo_id: cache write failed: {e}")

    return repo_id, "list", ""


def _skip_message_for_reason(reason: str, repo_name: str, saas_url: str) -> str:
    """User-facing explanation when pending-evidence pull is skipped."""
    if reason == "no_matching_repo":
        return (
            f"Evidence sync skipped: repo '{repo_name}' not found on "
            f"{saas_url.rstrip('/')}/dashboard. If you renamed the repo or "
            "changed 'git remote', open the dashboard and confirm the repo "
            "entry matches, then re-run cl_sync."
        )
    if reason == "list_repos_network_error":
        return (
            "Evidence sync skipped: could not reach dashboard to look up "
            "repo ID. Scan upload succeeded; retry cl_sync to pull evidence."
        )
    if reason.startswith("list_repos_http_"):
        code = reason.rsplit("_", 1)[-1]
        return (
            f"Evidence sync skipped: dashboard returned HTTP {code} on "
            "/api/v1/repos. Scan upload succeeded; check dashboard status and "
            "retry cl_sync."
        )
    if reason == "list_repos_invalid_json":
        return ("Evidence sync skipped: dashboard /repos response was malformed. "
                "Scan upload succeeded; report to support if this persists.")
    return f"Evidence sync skipped: {reason}"


def _run_pending_evidence_pull(project_path: str, saas_url: str, api_key: str,
                               repo_name: str, slog) -> tuple[dict, str, str]:
    """Glue between cl_sync and core.pending_evidence.

    Resolves repo_id (cache → list+match with cache invalidation on 404),
    then wires curl-based HTTP into the pull orchestrator.

    Returns (summary_dict, human_prompt_string, resolved_repo_id).
    On unresolvable errors, summary_dict has {"skipped": True, "reason": ...}
    and human_prompt_string explains to the user what to do.
    """
    from core.pending_evidence import (
        pull_pending_evidence,
        build_human_prompt,
        clear_cached_repo_id,
        RepoNotFoundError,
    )

    # Resolve repo_id (cache or list+match)
    repo_id, source, reason = _resolve_saas_repo_id(
        project_path, saas_url, api_key, repo_name, slog,
    )
    if not repo_id:
        msg = _skip_message_for_reason(reason, repo_name, saas_url)
        return ({"skipped": True, "reason": reason}, msg, "")

    def _build_http_get_json(rid: str):
        # list URL for THIS repo_id — a 404 against this exact URL signals
        # "cached repo_id is stale" (or repo was deleted dashboard-side).
        list_url_for_rid = f"{saas_url.rstrip('/')}/api/v1/repos/{rid}/pending-evidence"

        def http_get_json(url: str) -> dict | None:
            code, body = _curl_json("GET", url, api_key, timeout=15)
            if code == 200 and body:
                try:
                    return json.loads(body)
                except json.JSONDecodeError as e:
                    slog.error(f"pull GET {url}: invalid JSON: {e}")
                    return None
            if code == 404:
                if url == list_url_for_rid:
                    # Stale cache signal — caller decides whether to retry
                    raise RepoNotFoundError(url)
                slog.info(f"pull GET {url}: 404 (non-list; item gone)")
                return None
            if code == 410:
                slog.warning(f"pull GET {url}: 410 expired")
                return None
            if code == 0:
                slog.error(f"pull GET {url}: curl failed (no response)")
                return None
            slog.error(f"pull GET {url}: HTTP {code} body={body[:200]}")
            return None

        return http_get_json

    def http_post_json(url: str, payload: dict) -> dict | None:
        data = json.dumps(payload, default=str, ensure_ascii=True).encode("utf-8")
        code, body = _curl_json("POST", url, api_key, body=data, timeout=15)
        if code == 200 and body:
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                slog.error(f"sync-confirm: invalid JSON: {e}")
                return None
        if code == 0:
            slog.error(f"sync-confirm: curl failed (no response)")
            return None
        slog.error(f"sync-confirm: HTTP {code} body={body[:200]}")
        return None

    try:
        summary = pull_pending_evidence(
            project_path=project_path,
            saas_url=saas_url,
            repo_id=repo_id,
            http_get_json=_build_http_get_json(repo_id),
            http_post_json=http_post_json,
            logger=slog,
        )
    except RepoNotFoundError:
        # Cached repo_id was stale (or repo deleted). Invalidate + re-resolve
        # once. Do NOT retry indefinitely — if a fresh list+match still 404s,
        # the repo really is gone.
        if source != "cache":
            slog.error("repo_id from fresh list returned 404 — repo disappeared mid-sync")
            return ({"error": "repo_disappeared_mid_sync"},
                    "Evidence sync skipped: repo disappeared during sync. Retry cl_sync.",
                    repo_id)
        slog.warning(f"cached repo_id {repo_id} is stale — invalidating and retrying")
        clear_cached_repo_id(project_path)
        repo_id, source, reason = _resolve_saas_repo_id(
            project_path, saas_url, api_key, repo_name, slog, force_refresh=True,
        )
        if not repo_id:
            msg = _skip_message_for_reason(reason, repo_name, saas_url)
            # Annotate that we already invalidated a stale cache
            return ({"skipped": True, "reason": reason, "note": "cache_invalidated"},
                    msg, "")
        try:
            summary = pull_pending_evidence(
                project_path=project_path,
                saas_url=saas_url,
                repo_id=repo_id,
                http_get_json=_build_http_get_json(repo_id),
                http_post_json=http_post_json,
                logger=slog,
            )
        except RepoNotFoundError:
            slog.error("fresh repo_id also returned 404 — aborting")
            return ({"error": "repo_not_found_after_refresh"},
                    "Evidence sync skipped: repo not found on dashboard.", repo_id)

    return summary.to_dict(), build_human_prompt(summary), repo_id


def _run_broken_link_check(project_path: str, saas_url: str, api_key: str,
                           repo_id: str, checked_at_sha: str | None,
                           slog) -> dict:
    """Glue between cl_sync and core.broken_link.

    Wires curl-based HTTP into the broken_link sweep orchestrator.
    Returns a dict summary suitable for the cl_sync result payload.
    """
    from core.broken_link import run_broken_link_check

    def http_get_json(url: str) -> dict | None:
        code, body = _curl_json("GET", url, api_key, timeout=15)
        if code == 200 and body:
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                slog.error(f"broken_link GET {url}: invalid JSON: {e}")
                return None
        if code == 404:
            slog.info(f"broken_link GET {url}: 404 (no rows or repo gone)")
            return None
        if code == 0:
            slog.error(f"broken_link GET {url}: curl failed (no response)")
            return None
        slog.error(f"broken_link GET {url}: HTTP {code} body={body[:200]}")
        return None

    def http_post_json(url: str, payload: dict) -> dict | None:
        data = json.dumps(payload, default=str, ensure_ascii=True).encode("utf-8")
        code, body = _curl_json("POST", url, api_key, body=data, timeout=30)
        if code == 200 and body:
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                slog.error(f"broken_link POST: invalid JSON: {e}")
                return None
        if code == 0:
            slog.error("broken_link POST: curl failed (no response)")
            return None
        slog.error(f"broken_link POST: HTTP {code} body={body[:200]}")
        return None

    summary = run_broken_link_check(
        project_path=project_path,
        saas_url=saas_url,
        repo_id=repo_id,
        http_get_json=http_get_json,
        http_post_json=http_post_json,
        checked_at_sha=checked_at_sha,
        logger=slog,
    )
    return summary.to_dict()


def _check_latest_version() -> dict:
    """Check PyPI for the latest ComplianceLint version. Returns update info or empty dict."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://pypi.org/pypi/compliancelint/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            latest = data.get("info", {}).get("version", "")
            if latest and latest != CL_VERSION:
                return {
                    "update_available": True,
                    "current_version": CL_VERSION,
                    "latest_version": latest,
                    "upgrade_command": "pip install --upgrade compliancelint",
                }
            return {"update_available": False}
    except Exception:
        return {}


@mcp.tool()
def cl_delete(project_path: str, target: str = "local", confirm: bool = False) -> str:
    """Delete compliance scan data.

    Args:
        project_path: Project directory path.
        target: What to delete:
            - "local": Delete .compliancelint/ directory (local scan data)
            - "remote": Delete scan data from ComplianceLint Dashboard (requires API key)
            - "all": Delete both local and remote data
        confirm: Must be set to true to actually delete. First call without confirm
            returns a warning message.
    """
    import shutil

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    if target not in ("local", "remote", "all"):
        return json.dumps({"error": f"Invalid target: '{target}'. Must be 'local', 'remote', or 'all'."})

    from core.scanner_log import get_scanner_logger
    slog = get_scanner_logger(project_path)

    cl_dir = os.path.join(project_path, ".compliancelint")
    config = ProjectConfig.load(project_path)

    # Confirmation gate
    if not confirm:
        warning_parts = []
        if target in ("local", "all"):
            has_local = os.path.isdir(cl_dir)
            warning_parts.append(
                f"LOCAL: Will delete .compliancelint/ directory ({'exists' if has_local else 'not found'}). "
                "This removes all local scan data, baselines, and evidence."
            )
        if target in ("remote", "all"):
            has_key = bool(config.saas_api_key)
            warning_parts.append(
                f"REMOTE: Will delete scan data from dashboard ({'API key configured' if has_key else 'no API key — will fail'}). "
                "This removes all scans, findings, and history from the server."
            )
        return json.dumps({
            "status": "confirmation_required",
            "warning": " | ".join(warning_parts),
            "action": f"Call cl_delete(project_path, target='{target}', confirm=true) to proceed.",
        })

    results = {}

    # Delete local data
    if target in ("local", "all"):
        if os.path.isdir(cl_dir):
            shutil.rmtree(cl_dir)
            results["local"] = "deleted"
            slog.info("cl_delete: removed .compliancelint/ directory")
        else:
            results["local"] = "not_found"

    # Delete remote data (permanent purge — owner only)
    if target in ("remote", "all"):
        if not config.saas_api_key:
            results["remote"] = "error: no API key configured. Run cl_connect() first."
        else:
            saas_url = config.saas_url or "https://compliancelint.dev"
            config.derive_git_identity(project_path)
            repo_name = config.repo_name or os.path.basename(os.path.normpath(project_path))

            import subprocess
            curl_flags: dict = {"capture_output": True, "text": True, "timeout": 15}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                curl_flags["creationflags"] = subprocess.CREATE_NO_WINDOW

            try:
                # Step 1: Find the repo ID via repos list API
                list_url = f"{saas_url}/api/v1/repos"
                r = subprocess.run(
                    ["curl", "-s", "--max-time", "8",
                     "-H", f"Authorization: Bearer {config.saas_api_key}",
                     list_url],
                    **curl_flags,
                )
                if r.returncode != 0 or not r.stdout.strip():
                    results["remote"] = f"error: failed to list repos (exit {r.returncode})"
                else:
                    repos_list = json.loads(r.stdout.strip())
                    # Match by repo name
                    matched = [rp for rp in repos_list if rp.get("name") == repo_name]
                    if not matched:
                        results["remote"] = f"not_found: repo '{repo_name}' not found on dashboard"
                    else:
                        repo_id = matched[0]["id"]
                        # Step 2: Call purge endpoint
                        purge_url = f"{saas_url}/api/v1/repos/{repo_id}/purge"
                        payload = json.dumps({"confirmName": repo_name})
                        r2 = subprocess.run(
                            ["curl", "-s", "--max-time", "8", "-X", "DELETE",
                             "-H", f"Authorization: Bearer {config.saas_api_key}",
                             "-H", "Content-Type: application/json",
                             "-d", payload, purge_url],
                            **curl_flags,
                        )
                        if r2.returncode == 0 and r2.stdout.strip():
                            resp = json.loads(r2.stdout.strip())
                            results["remote"] = resp.get("status", "unknown")
                            if resp.get("error"):
                                results["remote"] = f"error: {resp['error']}"
                        else:
                            results["remote"] = f"error: purge request failed (exit {r2.returncode})"
            except Exception as e:
                results["remote"] = f"error: {e}"
            slog.info("cl_delete: remote purge result=%s", results.get("remote"))

    return json.dumps({"status": "deleted", "results": results})


@mcp.tool()
def cl_disconnect(project_path: str) -> str:
    """Disconnect from ComplianceLint Dashboard.

    Removes API key and connection config from .compliancelintrc.
    Local scan data in .compliancelint/ is preserved.

    Args:
        project_path: Project directory path.
    """
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    from core.scanner_log import get_scanner_logger
    slog = get_scanner_logger(project_path)

    config_path = os.path.join(project_path, ".compliancelintrc")
    if not os.path.isfile(config_path):
        return json.dumps({"status": "not_connected", "message": "No .compliancelintrc found."})

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return json.dumps({"error": "Could not read .compliancelintrc.", "fix": "Check that .compliancelintrc is valid JSON."})

    # Remove connection fields, keep local config
    removed = []
    for field in ("saas_api_key", "saas_url", "auto_sync"):
        if field in data:
            del data[field]
            removed.append(field)

    if not removed:
        return json.dumps({"status": "not_connected", "message": "No dashboard connection found in .compliancelintrc."})

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
        f.write("\n")

    slog.info("cl_disconnect: removed fields=%s", removed)

    return json.dumps({
        "status": "disconnected",
        "removed_fields": removed,
        "preserved": [k for k in data.keys()],
        "message": "Disconnected from dashboard. Local scan data in .compliancelint/ is preserved.",
    })


@mcp.tool()
def cl_version() -> str:
    """Return ComplianceLint scanner version and check for updates."""
    result = {"version": CL_VERSION, "tools": 16}
    update_info = _check_latest_version()
    if update_info:
        result.update(update_info)
    return json.dumps(result)


def main():
    """Entry point for `compliancelint-server` console script (pip install)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
