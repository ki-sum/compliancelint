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

CL_VERSION = "1.0.0"  # ComplianceLint version — displayed in UI, PDF, and scan metadata

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

    Step 3: Fill in compliance_answers based on COMPLETE code reading:
      {
        "ai_model": "<REQUIRED — your model ID, e.g. claude-sonnet-4-6>",
        "art5": {
          "is_realtime_processing": true | false | null,
          "prohibited_practices": [
            {"practice": "biometric_surveillance", "detected": false,
             "evidence": "read all X files, found no biometric code",
             "evidence_paths": [], "confidence": "high"},
            ...
          ]
        },
        "art9": { "has_risk_docs": true, "risk_doc_paths": ["docs/risk.md"], ... },
        "art12": { "has_logging": true, "logging_description": "structlog", ... },
        ... (see context.py for full schema)
      }

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
            - "eu-ai-act" (default) — EU AI Act (Regulation 2024/1689)
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
            "supported": ["eu-ai-act"],
            "coming_soon": ["gdpr", "nist-ai-rmf", "iso-42001"],
        })

    # Parse project context
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid project_context JSON: {e}"})

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
            "hint": "Use 'all', a single number (e.g. '12'), comma-separated (e.g. '9,12,14'), or JSON array (e.g. '[9,12,14]')",
        })

    # Save AI provider metadata if provided
    if ai_provider:
        from core.state import save_metadata
        save_metadata(project_path, ai_provider=ai_provider)

    # Single article → return full findings + post-scan hint
    if len(article_numbers) == 1:
        output = _scan_single_article(article_numbers[0], project_path, context=ctx)
        config = ProjectConfig.load(project_path)
        if config.saas_api_key and config.auto_sync:
            try:
                sync_result = cl_sync(project_path)
                sync_data = json.loads(sync_result)
                if sync_data.get("status") == "synced":
                    output += "\n\n--- Results synced to dashboard ---"
            except Exception:
                pass
        else:
            output += _build_post_scan_hint(project_path)
        return output

    # Multiple articles → scan each and return combined result
    results = {}
    for art_num in article_numbers:
        result_json = _scan_single_article(art_num, project_path, context=ctx)
        try:
            result_data = json.loads(result_json)
            results[f"article_{art_num}"] = result_data
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
        except Exception:
            pass
    else:
        output += _build_post_scan_hint(project_path)

    return output


@mcp.tool()
def cl_explain(regulation: str = "eu-ai-act", article: int = 0) -> str:
    """Explain a regulation article in plain language.

    Args:
        regulation: Which regulation (default: "eu-ai-act").
        article: Article number to explain (e.g. 12 for Article 12).
    """
    if regulation != "eu-ai-act":
        return json.dumps({"error": f"Regulation '{regulation}' not yet supported."})
    return cl_explain_article(article)


@mcp.tool()
def cl_report(
    project_path: str,
    regulation: str = "",
    format: str = "md",
) -> str:
    """Export a compliance report.

    Args:
        project_path: Absolute path to the project directory.
        regulation: Filter by regulation (empty = all regulations in state).
        format: Report format — "md" (Markdown) or "json".
    """
    return cl_export_report(project_path, format)


# ── Legacy per-article tools (backward compatibility) ─────────────────────
# These delegate to cl_scan(). They will be deprecated in a future version.

@mcp.tool()
def cl_scan_article_5(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 5 (Prohibited Practices) compliance.

    Checks for code patterns that may indicate prohibited AI practices:
    - Subliminal manipulation or dark patterns targeting vulnerabilities
    - Social scoring systems
    - Real-time biometric identification in public spaces
    - Emotion inference in workplace/education contexts

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(5, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_6(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 6 (High-Risk Classification) compliance.

    Determines whether the system falls under Annex III high-risk categories:
    - Biometric identification/categorisation
    - Critical infrastructure management
    - Education and vocational training
    - Employment and worker management
    - Access to essential services
    - Law enforcement
    - Migration and border control
    - Administration of justice

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(6, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_9(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 9 (Risk Management System) compliance.

    Checks for:
    - Risk management documentation (risk register, risk assessment)
    - Intended use and foreseeable misuse documentation
    - Residual risk documentation
    - Testing against pre-defined metrics
    - Post-market monitoring integration

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(9, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_10(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 10 (Data Governance) compliance.

    Checks for:
    - Dataset documentation (data cards, datasheets)
    - Data pipeline and preprocessing documentation
    - Bias detection tooling
    - Data versioning and traceability
    - Train/validation/test split documentation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(10, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_11(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 11 (Technical Documentation) compliance.

    Checks for:
    - System description and intended purpose (README/docs)
    - Architecture documentation
    - API specification
    - Model card with training/evaluation details
    - Testing and change log documentation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(11, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_12(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 12 (Record-keeping) compliance.

    Performs static analysis to check:
    - Logging framework presence and type
    - API endpoint logging coverage
    - Structured log fields (timestamp, user_id, action, etc.)
    - Log retention policy (Art. 19 requires >= 6 months)
    - Tamper protection mechanisms

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(12, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_13(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 13 (Transparency) compliance.

    Checks for:
    - User/deployer documentation (instructions of use)
    - Model interpretability tooling (SHAP, LIME, etc.)
    - Confidence/uncertainty scores in outputs
    - Documented intended purpose
    - Known limitations documentation
    - Input data specifications

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(13, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_14(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 14 (Human Oversight) compliance.

    Checks for:
    - Human-in-the-loop patterns (approval flows, review queues)
    - Override and kill-switch mechanisms
    - Monitoring dashboard components
    - Alert and notification systems
    - Automation bias awareness measures
    - Confidence-based escalation to human review

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(14, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_15(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 15 (Accuracy, Robustness & Cybersecurity) compliance.

    Checks for:
    - Accuracy metrics and testing infrastructure
    - Input validation and error handling
    - Rate limiting and authentication/authorization
    - Dependency vulnerability scanning
    - Adversarial testing patterns
    - Redundancy and failover configuration

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(15, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_16(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 16 (Obligations of providers of high-risk AI systems) compliance.

    Checks for:
    - Section 2 compliance (Art. 8-15 requirements)
    - Provider identification on system/packaging/documentation
    - Quality management system (Art. 17)
    - Documentation keeping (Art. 18)
    - Log retention (Art. 19)
    - Conformity assessment (Art. 43)
    - EU declaration of conformity (Art. 47)
    - CE marking (Art. 48)
    - EU database registration (Art. 49)
    - Corrective actions process (Art. 20)
    - Conformity demonstrability on authority request
    - Accessibility requirements compliance

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(16, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_50(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 50 (Transparency for General-Purpose AI) compliance.

    Checks for:
    - AI interaction disclosure (chatbot/assistant identification)
    - C2PA content credentials for AI-generated media
    - Machine-readable AI-generation markers
    - Deep fake disclosure mechanisms
    - Emotion recognition / biometric categorisation notice

    NOTE: Art. 50 applies broadly — almost ALL AI-facing user interfaces
    must comply. Enforcement began August 2025.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(50, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_4(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 4 (AI Literacy) compliance.

    Checks for:
    - AI literacy programs and training documentation
    - AI usage policies for staff
    - Competency frameworks mentioning AI

    NOTE: Art. 4 applies to ALL AI systems (not just high-risk).
    Enforcement began February 2025.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(4, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_17(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 17 (Quality Management System) compliance.

    Checks for:
    - Documented QMS (policies, procedures, instructions)
    - Regulatory compliance strategy
    - Design, QA, and testing procedures
    - Data management systems
    - Accountability framework

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(17, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_18(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 18 (Documentation keeping) compliance.

    Checks for:
    - Documentation retention policy (10-year minimum)
    - Technical documentation retention (Art. 11)
    - QMS documentation retention (Art. 17)
    - EU declaration of conformity retention (Art. 47)
    - Financial institution documentation integration (conditional)

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(18, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_19(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 19 (Automatically generated logs) compliance.

    Checks for:
    - Log retention by provider (Art. 12(1) logs kept under provider control)
    - Minimum six-month retention period
    - Retention period appropriate to intended purpose
    - Financial institution log integration (conditional)

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(19, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_26(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 26 (Deployer Obligations) compliance.

    Checks for:
    - Use per provider instructions
    - Human oversight assignment to competent persons
    - Operational monitoring
    - Log retention (>= 6 months)
    - Affected person notification

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(26, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_27(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 27 (Fundamental Rights Impact Assessment) compliance.

    Checks for:
    - FRIA documentation covering six required elements
    - FRIA versioning and pre-deployment dating
    - Authority notification (manual)
    - DPIA complementarity (conditional, manual)

    NOTE: Art. 27 applies to deployers that are public law bodies, private entities
    providing public services, or deployers of Annex III point 5(b) and (c) systems.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(27, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_72(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 72 (Post-Market Monitoring by Providers) compliance.

    Checks for:
    - Post-market monitoring system documentation
    - Active data collection and compliance evaluation
    - Post-market monitoring plan (Annex IV)
    - Integration with existing monitoring (Annex I products)

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(72, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_73(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 73 (Reporting of Serious Incidents) compliance.

    Checks for:
    - Incident reporting procedures and authority contact information
    - Reporting timelines (15 days general, 2 days widespread, 10 days death)
    - Expedited reporting procedures for severe incidents
    - Investigation procedures with risk assessment and corrective action

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(73, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_86(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 86 (Right to Explanation of Individual Decision-Making) compliance.

    Checks for:
    - Explanation mechanisms for AI-assisted decisions
    - Clear and meaningful explanation of AI system's role in decision-making
    - Explanation of main elements of decisions taken
    - User-facing explainability interfaces

    NOTE: Art. 86 applies to deployers of Annex III high-risk systems (excluding
    point 2) that produce legal effects or similarly significant effects.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(86, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_20(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 20 (Corrective actions and duty of information) compliance.

    Checks for:
    - Corrective action procedures (bring into conformity, withdraw, disable, recall)
    - Supply chain notification mechanisms (distributors, deployers, authorised representatives)
    - Risk investigation procedures and authority notification protocols

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(20, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_41(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 41 (Common specifications) compliance.

    Checks for:
    - Standards compliance documentation or alternative technical solution justification
    - Documented justification when provider does not follow common specifications

    NOTE: Art. 41 applies to providers of high-risk AI systems only.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(41, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_43(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 43 (Conformity Assessment) compliance.

    Checks for:
    - Conformity assessment documentation (Annex VI or VII)
    - Substantial modification tracking / change management

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(43, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_47(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 47 (EU Declaration of Conformity) compliance.

    Checks for:
    - Written EU Declaration of Conformity document
    - Machine-readable format
    - Annex V content coverage
    - 10-year retention plan

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(47, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_49(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 49 (Registration) compliance.

    Checks for:
    - EU database registration documentation
    - Registration ID / confirmation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(49, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_51(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 51 (GPAI Classification) compliance.

    Checks for:
    - Systemic risk classification (10^25 FLOPs threshold)
    - High impact capability evaluation

    NOTE: Art. 51-55 apply to GPAI model providers, not downstream integrators.
    Enforcement began August 2025.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(51, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_52(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 52 (GPAI Notification Procedure) compliance.

    Checks for:
    - Commission notification for systemic risk models
    - Notification documentation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(52, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_53(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 53 (GPAI Provider Obligations) compliance.

    Checks for:
    - Model technical documentation (Annex XI)
    - Downstream provider documentation (Annex XII)
    - Copyright compliance policy
    - Public training data summary

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(53, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_54(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 54 (GPAI Authorised Representatives) compliance.

    Checks for:
    - Authorised representative appointment (third-country providers)
    - Written mandate documentation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(54, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_55(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 55 (GPAI Systemic Risk) compliance.

    Checks for:
    - Adversarial testing / red-teaming
    - Systemic risk assessment
    - Incident tracking and reporting
    - Model cybersecurity measures

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(55, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_21(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 21 (Cooperation with competent authorities) compliance.

    Checks for:
    - Compliance documentation availability for authority requests
    - Log export mechanisms for authority access

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(21, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_22(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 22 (Authorised Representatives) compliance.

    Checks for:
    - Authorised representative appointment for non-EU providers
    - Representative enablement and mandate documentation
    - Authority contact information in mandate

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(22, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_23(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 23 (Obligations of importers) compliance.

    Checks for:
    - Pre-market conformity verification (Art. 43, Art. 11, CE marking, Art. 47, Art. 22(1))
    - Conformity review procedures (non-placement of non-conforming systems)
    - Importer identification on system/packaging/documentation
    - Documentation retention (10 years)
    - Authority documentation capability
    - Storage/transport conditions
    - Authority cooperation

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(23, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_24(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 24 (Obligations of distributors) compliance.

    Checks for:
    - Pre-market verification (CE marking, EU declaration, instructions)
    - Conformity review procedures
    - Authority documentation capability
    - Storage/transport conditions
    - Corrective action procedures

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(24, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_25(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 25 (Responsibilities along the AI value chain) compliance.

    Checks for:
    - Rebranding/modification triggering provider status (Art. 25(1))
    - Initial provider cooperation documentation (Art. 25(2))
    - Product manufacturer classification for Annex I safety components (Art. 25(3))
    - Written agreements with third-party AI suppliers (Art. 25(4))
    - IP and trade secret protection (Art. 25(5))

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(25, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_60(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 60 (Testing of high-risk AI systems in real world conditions outside AI regulatory sandboxes) compliance.

    Checks for:
    - Real-world testing plan drawn up and submitted to market surveillance authority
    - Authority approval for testing in real world conditions
    - Registration in EU database with unique identification number
    - Serious incident reporting procedures during testing
    - Testing suspension/termination notification procedures

    NOTE: Art. 60 applies only to providers conducting real-world testing of Annex III
    high-risk AI systems outside regulatory sandboxes.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(60, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_61(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 61 (Informed consent to participate in testing in real world conditions) compliance.

    Checks for:
    - Freely-given informed consent procedures for real-world testing subjects
    - Information disclosure covering nature/objectives, conditions/duration, rights, reversal, and ID/contact
    - Consent documentation (dated, documented, copy given to subject)

    NOTE: Art. 61 applies only to providers conducting real-world testing of Annex III
    high-risk AI systems outside regulatory sandboxes under Art. 60.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(61, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_71(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 71 (EU database for high-risk AI systems listed in Annex III) compliance.

    Checks for:
    - Provider data entry in EU database (Annex VIII Sections A and B)
    - Public-authority deployer data entry (Annex VIII Section C)

    NOTE: Art. 71 applies to providers of high-risk AI systems listed in Annex III
    and to deployers who are public authorities.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(71, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_80(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 80 (Procedure for dealing with AI systems classified by the provider as non-high-risk in application of Annex III) compliance.

    Checks for:
    - Compliance remediation plan when system is reclassified as high-risk
    - Corrective action covering all affected systems on the Union market
    - Classification rationale documentation to demonstrate non-deliberate misclassification

    NOTE: Art. 80 applies to providers whose AI system was classified as non-high-risk
    under Art. 6(3) but is found by market surveillance authorities to present a risk.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(80, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_82(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 82 (Compliant AI systems which present a risk) compliance.

    Checks for:
    - Corrective action plans covering all affected systems on the Union market
    - Corrective action taken within the timeline prescribed by the market surveillance authority

    NOTE: Art. 82 applies to providers of compliant high-risk AI systems that are
    nonetheless found by market surveillance authorities to present a risk.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(82, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_91(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 91 (Power to request documentation and information) compliance.

    Checks for:
    - GPAI model documentation readiness (Art. 53/55 documentation completeness)
    - Information request response procedures

    NOTE: Art. 91 applies to providers of general-purpose AI models when requested
    by the Commission during investigations.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(91, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_92(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 92 (Power to conduct evaluations) compliance.

    Checks for:
    - GPAI model evaluation cooperation readiness
    - Evaluation response procedures and documentation

    NOTE: Art. 92 applies to providers of general-purpose AI models during
    Commission evaluations.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(92, project_path, context=ctx)


@mcp.tool()
def cl_scan_article_111(project_path: str, project_context: str = "") -> str:
    """Scan a project for EU AI Act Article 111 (Transitional Provisions) compliance.

    Checks for:
    - Annex X legacy system transition planning
    - Significant change tracking for pre-existing high-risk systems
    - GPAI model compliance timeline tracking

    NOTE: Art. 111 applies to AI systems and GPAI models already placed on
    the market before the EU AI Act's application dates.

    Args:
        project_path: Absolute path to the project directory to scan.
        project_context: Optional JSON string with AI-enriched project context.
    """
    ctx = None
    if project_context:
        try:
            ctx = ProjectContext.from_json(project_context)
        except (json.JSONDecodeError, TypeError):
            pass
    return _scan_single_article(111, project_path, context=ctx)


@mcp.tool()
def cl_scan_all(project_path: str, project_context: str = "", ai_provider: str = "") -> str:
    """Scan a project for ALL available EU AI Act compliance checks.

    Returns a SUMMARY report — one row per article with overall status and
    top findings. Full findings are available via cl_scan_article_N tools.

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
            )
        })
    try:
        ctx = ProjectContext.from_json(project_context)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"Invalid project_context JSON: {e}"})

    # Lazy-load all modules now (deferred from startup)
    logger.info("cl_scan_all — loading all modules...")
    _ensure_all_modules_loaded()
    logger.info("cl_scan_all — %d modules loaded, starting scan...", len(_modules))

    # Load project config (.compliancelintrc) and make available to all modules
    config = ProjectConfig.load(project_path)
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
                "note": f"Call cl_scan_article_{art_num}() for full findings.",
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
                    "error": f"Scan timed out after {_ARTICLE_TIMEOUT_SECS}s",
                    "overall": "unable_to_determine",
                    "note": f"Call cl_scan_article_{art_num}() directly to retry.",
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
    output = json.dumps(report, indent=2, default=str)

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
        except Exception:
            pass  # Non-blocking — silently skip on failure
    else:
        output += _build_post_scan_hint(project_path, nc_count=nc_total)

    return output


@mcp.tool()
def cl_explain_article(article_number: int) -> str:
    """Explain what a specific EU AI Act article requires, in plain language.

    Provides:
    - The official requirement summary
    - What can be automated vs. needs human judgment
    - The ComplianceLint compliance checklist (where official standards don't exist yet)
    - Cross-references to related articles

    Args:
        article_number: The article number (e.g., 12 for Article 12).
    """
    _ensure_module_loaded(article_number)

    if article_number in _modules:
        explanation = _modules[article_number].explain()
        return explanation.to_json()

    return json.dumps({
        "error": f"Article {article_number} explanation not yet available.",
        "available_articles": sorted(_modules.keys()),
        "note": "More articles will be added progressively.",
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
        return json.dumps({"error": f"Regulation '{regulation}' not yet supported."})

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    _ensure_all_modules_loaded()

    all_actions = []
    articles_covered = []

    target_articles = [article] if article > 0 else sorted(_modules.keys())
    for art_num in target_articles:
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
            "note": "The module exists but its interim-standard.json is missing.",
        })

    return json.dumps({
        "error": f"No module available for Article {article_number}.",
        "available": sorted(_modules.keys()),
        "note": "More compliance checklist will be added as articles are decomposed.",
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
    # Read attester identity (config > git config > reject)
    from core.config import ProjectConfig
    config = ProjectConfig.load(project_path)
    attester = config.get_attester(project_path)

    if attester is None:
        return json.dumps({
            "error": "Cannot attest without identity. "
                     "Set attester in .compliancelintrc: "
                     '{"attester": {"name": "Your Name", "email": "you@company.com", "role": "CTO"}} '
                     "or configure git user.name and user.email.",
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
def cl_export_report(project_path: str, format: str = "md") -> str:
    """Export the compliance state as a formatted report.

    Reads .compliancelint/state.json and generates a report file.
    Requires a previous scan (state.json must exist).

    Supported formats:
      - md: Markdown report with tables
      - json: Raw JSON state dump

    Args:
        project_path: Absolute path to the project directory.
        format: Report format — "md" or "json".
    """
    from core.state import export_report
    result = export_report(project_path, fmt=format)
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
            "evidence_file": evidence.evidence_file,
        })

    if not evidence.has_evidence:
        return json.dumps({
            "evidence_file": evidence.evidence_file,
            "found": False,
            "message": (
                "No compliance-evidence.json found in project root. "
                "Create this file to declare evidence for obligations that cannot be "
                "detected from source code alone (e.g., external Terms of Service, "
                "Privacy Policy URLs, configuration screenshots)."
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

def _scan_single_article(article_number: int, project_path: str, context=None) -> str:
    """Scan a project for a specific article's compliance."""
    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    # Lazy-load the module if not yet loaded
    logger.info("Art. %d — loading module...", article_number)
    _ensure_module_loaded(article_number)

    if article_number not in _modules:
        return json.dumps({
            "error": f"Article {article_number} module not available.",
            "available": sorted(_modules.keys()),
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
            "article": article_number,
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
def cl_connect(project_path: str, email: str = "", switch_account: bool = False) -> str:
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
    import webbrowser
    import http.server
    import threading

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    config = ProjectConfig.load(project_path)
    saas_url = config.saas_url or "https://compliancelint.dev"

    # Backfill repo_name/project_id if missing (upgrade from older cl_connect)
    # Use a separate Python subprocess to avoid blocking MCP asyncio event loop
    if not config.repo_name or not config.project_id:
        try:
            import subprocess as _sp_bf
            _bf_script = (
                f"import sys; sys.path.insert(0, {repr(os.path.dirname(os.path.abspath(__file__)))}); "
                f"from core.config import ProjectConfig; "
                f"c = ProjectConfig.load({repr(project_path)}); "
                f"c.derive_git_identity({repr(project_path)}); "
                f"c.save({repr(project_path)})"
            )
            _bf_flags = {"capture_output": True, "text": True, "timeout": 5}
            if hasattr(_sp_bf, "CREATE_NO_WINDOW"):
                _bf_flags["creationflags"] = _sp_bf.CREATE_NO_WINDOW
            _bf_result = _sp_bf.run(["python", "-c", _bf_script], **_bf_flags)
            if _bf_result.returncode == 0:
                # Reload config to pick up backfilled values
                config = ProjectConfig.load(project_path)
            else:
                logger.warning("Backfill subprocess failed (rc=%d): %s", _bf_result.returncode, _bf_result.stderr[:200])
        except Exception as _bf_err:
            logger.warning("Backfill subprocess error: %s", _bf_err)

    # If already connected (and not switching), check if key still works
    if config.saas_api_key and not switch_account:
        try:
            import subprocess as _sp_chk
            check_url = f"{saas_url}/api/v1/auth/check"
            _curl_flags = {}
            if hasattr(_sp_chk, "CREATE_NO_WINDOW"):
                _curl_flags["creationflags"] = _sp_chk.CREATE_NO_WINDOW
            _chk = _sp_chk.run(
                ["curl", "-s", "--max-time", "5", "-H", f"Authorization: Bearer {config.saas_api_key}", check_url],
                capture_output=True, text=True, timeout=8, **_curl_flags,
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

    # ── Browser OAuth flow ──
    # 1. Start a temporary local HTTP server to receive the API key callback
    # 2. Open browser to dashboard connect page with callback port
    # 3. User signs in with GitHub/Google
    # 4. Dashboard redirects to localhost with API key
    # 5. Local server captures key and saves to .compliancelintrc

    received_key = {"api_key": "", "email": "", "error": ""}

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            """Handle the OAuth callback with API key."""
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            received_key["api_key"] = query.get("api_key", [""])[0]
            received_key["email"] = query.get("email", [""])[0]
            received_key["error"] = query.get("error", [""])[0]

            # Send a nice HTML response to close the browser tab
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
                body { background: #09090A; color: #e2e8f0; font-family: system-ui;
                       display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { text-align: center; }
                .ok { color: #10b981; font-size: 48px; }
                .err { color: #ef4444; font-size: 48px; }
                h1 { margin-top: 16px; }
                p { color: #94a3b8; }
            </style></head><body><div class="card">"""

            dashboard_url = f"{saas_url}/dashboard"
            if received_key["api_key"]:
                html += '<div class="ok">✓</div><h1>Connected!</h1>'
                html += "<p>Redirecting to dashboard...</p>"
                html += '<p>Run <code>cl_sync()</code> or tell your AI: <em>"Sync my scan results"</em></p>'
                html += f'<script>setTimeout(function(){{ window.location.href="{dashboard_url}"; }}, 2000);</script>'
            else:
                err = received_key["error"] or "Unknown error"
                html += f'<div class="err">✗</div><h1>Connection Failed</h1><p>{err}</p>'

            html += "</div></body></html>"
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, format, *args):
            pass  # Suppress HTTP log output

    # Find an available port
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Start local server in a thread
    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    def serve_once():
        server.handle_request()  # Handle exactly one request then stop

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()

    # Open browser to dashboard connect page
    connect_url = f"{saas_url}/api/v1/auth/connect?callback=http://127.0.0.1:{port}/callback"
    logger.info("Opening browser for authentication: %s", connect_url)

    try:
        webbrowser.open(connect_url)
    except Exception:
        server.server_close()
        return json.dumps({
            "error": "Could not open browser.",
            "hint": f"Open this URL manually: {connect_url}",
        })

    # Wait for the callback (up to 2 minutes)
    logger.info("Waiting for authentication callback on port %d...", port)
    thread.join(timeout=120)
    server.server_close()

    if not received_key["api_key"]:
        if received_key["error"]:
            return json.dumps({"error": f"Authentication failed: {received_key['error']}"})
        return json.dumps({
            "error": "Timed out waiting for authentication.",
            "hint": "Make sure you completed the sign-in in your browser.",
        })

    # Save API key + repo identity to .compliancelintrc
    config.saas_api_key = received_key["api_key"]
    config.saas_url = saas_url

    # Auto-derive repo_name + project_id so cl_sync never needs slow git lookups
    config.derive_git_identity(project_path)

    config_path = config.save(project_path)

    # Auto-add .compliancelintrc to .gitignore (prevent API key leaks)
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
    except Exception:
        pass  # Non-fatal: user can add manually

    email_display = received_key["email"] or "your account"

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
    # Debug: trace every step to file
    import sys
    _log_path = "c:/AI/ComplianceLint/cl_upload_debug.log"
    def _dbg_log(msg):
        with open(_log_path, "a") as _f:
            from datetime import datetime as _dt
            _f.write(f"{_dt.now().isoformat()} {msg}\n")
            _f.flush()
    _dbg_log(f"STEP 1: ENTERED project_path={project_path}")

    if not os.path.isdir(project_path):
        return json.dumps({"error": f"Directory not found: {project_path}"})

    # Load config for API key
    _dbg_log("STEP 2: loading config")
    config = ProjectConfig.load(project_path)
    _dbg_log(f"STEP 3: config loaded, api_key={config.saas_api_key[:10] if config.saas_api_key else 'NONE'}...")
    if not config.saas_api_key:
        return json.dumps({
            "error": "No API key configured. Run cl_connect() first to link your dashboard account.",
            "hint": "Run cl_connect() — it opens your browser to sign in.",
        })

    saas_url = config.saas_url or "https://compliancelint.dev"

    # Get project identity — reads config cache, never blocks on git in cl_sync
    _dbg_log("STEP 3b: loading project_id")
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
    _dbg_log(f"STEP 3c: project_id={project_id}")

    # Load scan state
    _dbg_log("STEP 4: loading state")
    state = load_state(project_path)
    _dbg_log(f"STEP 5: state loaded, articles={list(state.get('articles',{}).keys())}")

    if not state.get("articles"):
        return json.dumps({
            "error": "No scan results found. Run a scan first (e.g., cl_scan_article_9).",
            "hint": "Scan at least one article before syncing to the dashboard.",
        })

    # Derive repo name: config > git remote > directory name
    _dbg_log("STEP 6: deriving repo name")
    repo_name = config.repo_name
    if not repo_name:
        # Try git remote origin URL → extract "org/repo"
        try:
            import subprocess
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=project_path, timeout=2,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if ":" in url and "@" in url:
                    repo_name = url.split(":")[-1].replace(".git", "")
                elif "/" in url:
                    parts = url.rstrip("/").replace(".git", "").split("/")
                    if len(parts) >= 2:
                        repo_name = f"{parts[-2]}/{parts[-1]}"
        except Exception:
            pass
    if not repo_name:
        repo_name = os.path.basename(os.path.normpath(project_path))
    _dbg_log(f"STEP 6b: repo_name={repo_name}")

    # Load attestation responses from state.json findings history/evidence
    _dbg_log("STEP 7: loading attestation responses from state")
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
    except Exception:
        pass
    _dbg_log(f"STEP 7b: {len(response_items)} attestation responses loaded")

    # Load changes_summary if the AI wrote one (VCS-agnostic change tracking)
    _dbg_log("STEP 7c: loading changes_summary")
    changes_summary = ""
    changes_file = os.path.join(project_path, ".compliancelint", "changes_summary.txt")
    if os.path.isfile(changes_file):
        try:
            with open(changes_file, "r", encoding="utf-8") as _f:
                changes_summary = _f.read().strip()
            _dbg_log(f"STEP 7d: changes_summary loaded ({len(changes_summary)} chars)")
        except Exception:
            pass

    # Apply attestation overrides: rebutted → not_applicable, evidenced → compliant
    articles_data = json.loads(json.dumps(state.get("articles", {})))  # deep copy
    for _art_key, art_data in articles_data.items():
        for _obl_id, finding in (art_data.get("findings") or {}).items():
            if isinstance(finding, dict):
                if finding.get("suppression"):
                    finding["level"] = "not_applicable"
                elif finding.get("evidence") and len(finding["evidence"]) > 0:
                    finding["level"] = "compliant"

    # Build payload matching the API schema
    payload = {
        "project_id": project_id,
        "repo": repo_name,
        "scanned_at": state.get("last_scan", datetime.now(timezone.utc).isoformat()),
        "scanner_version": CL_VERSION,
        "regulation": state.get("regulation", "eu-ai-act"),
        "ai_provider": state.get("ai_provider"),
        "changes_summary": changes_summary or None,
        "articles": articles_data,
        "responses": response_items,  # Finding responses / attestations from state.json
    }

    # POST to dashboard
    scans_url = f"{saas_url}/api/v1/scans"
    # ensure_ascii=True: prevent mojibake (â€") when Alpine Docker decodes UTF-8 bytes
    data = json.dumps(payload, default=str, ensure_ascii=True).encode("utf-8")
    _dbg_log(f"STEP 8: about to POST {len(data)} bytes to {scans_url}")

    resp_data = {}

    try:
        _dbg_log("STEP 9: sending HTTP request via subprocess...")
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

        _dbg_log(f"STEP 10: HTTP done, code={http_code}, body={body_str[:200]}")

        if http_code == 401:
            return json.dumps({
                "error": "API key is invalid or expired.",
                "hint": "Run cl_connect again to generate a new API key.",
            })
        if http_code == 403:
            detail = ""
            try:
                detail = json.loads(body_str).get("error", body_str)
            except Exception:
                detail = body_str
            return json.dumps({
                "error": f"Dashboard returned HTTP 403: {detail}",
                "hint": "You may have reached your plan's repo limit. Check your dashboard settings.",
            })
        if http_code >= 400:
            return json.dumps({
                "error": f"Dashboard returned HTTP {http_code}",
                "detail": body_str[:500],
            })
        if body_str:
            resp_data = json.loads(body_str)

    except _sp.TimeoutExpired:
        return json.dumps({
            "error": f"Request to {saas_url} timed out after 15 seconds.",
            "hint": "Check your internet connection or try again.",
        })
    except Exception as e:
        _dbg_log(f"STEP 10-ERR: {e}")
        return json.dumps({"error": f"Sync failed: {e}"})

    dashboard_url = resp_data.get("dashboard_url", f"{saas_url}/dashboard")
    scan_id = resp_data.get("scan_id", "")

    result = json.dumps({
        "status": "synced",
        "scan_id": scan_id,
        "dashboard_url": dashboard_url,
        "articles_synced": list(state.get("articles", {}).keys()),
        "message": f"Scan results uploaded. View at: {dashboard_url}",
    })
    _dbg_log(f"STEP 11: returning result ({len(result)} bytes)")
    return result


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
def cl_version() -> str:
    """Return ComplianceLint scanner version and check for updates."""
    result = {"version": CL_VERSION, "tools": 24}
    update_info = _check_latest_version()
    if update_info:
        result.update(update_info)
    return json.dumps(result)


def main():
    """Entry point for `compliancelint-server` console script (pip install)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
