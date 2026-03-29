"""
Unified protocol for all EU AI Act article modules.

Every article module must implement ArticleModule to be auto-discovered
and registered by the MCP server.

Includes shared scanning utilities in BaseArticleModule to eliminate
code duplication across modules and ensure consistent behavior.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Optional, runtime_checkable


# ── Shared Enums ──

class ComplianceLevel(str, Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNABLE_TO_DETERMINE = "unable_to_determine"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutomationLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    MANUAL = "manual"


# ── Canonical Constants ──

# ── FALLBACK Constants ──
# These are DEFAULTS used when no AI context is available.
# When AI context IS available (via ProjectContext), modules should
# prefer context-provided values over these hardcoded lists.
#
# These lists will NOT be expanded. If a new language/framework is needed,
# the AI context provides it. Adding to these lists is an anti-pattern.

SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "target", "build", "dist", ".tox", ".mypy_cache",
    ".pytest_cache", ".next", ".nuxt", "vendor",
    "site-packages", ".eggs",
})

# FALLBACK: skip only noise dirs for AST analysis. AI context overrides.
SKIP_DIRS_COMPLIANCE = frozenset({
    "benchmarks", "benchmark", "perf",
    "fixtures", "testdata", "test_data",
    "stubs", "typestubs",
})

# FALLBACK: file type classification. AI context overrides.
SOURCE_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".mjs", ".cjs", ".cs",
})

DOC_EXTS = frozenset({
    ".md", ".txt", ".rst", ".pdf", ".docx", ".xlsx", ".csv",
})

CONFIG_EXTS = frozenset({
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
})

TEMPLATE_EXTS = frozenset({
    ".html", ".htm", ".hbs", ".ejs", ".jinja", ".jinja2",
    ".njk", ".pug", ".jade", ".mustache", ".twig", ".vue", ".svelte",
})

ALL_SCANNABLE_EXTS = SOURCE_EXTS | DOC_EXTS | CONFIG_EXTS | TEMPLATE_EXTS

# Comment line prefixes per language (for skip-comments feature)
_COMMENT_PREFIXES = ("#", "//", "*", "/*", "<!--", "---")


# ── Shared Data Structures ──

class GapType(str, Enum):
    """Whether a finding is about code or organizational process."""
    CODE = "code"          # Must be in the codebase (logging, error handling, etc.)
    PROCESS = "process"    # May be managed externally (risk docs, data governance, etc.)
    TECHNICAL = "technical"  # Technical implementation (accuracy metrics, security, etc.)


@dataclass
class Finding:
    """A single compliance finding from a scan."""
    obligation_id: str
    file_path: str
    line_number: Optional[int]
    level: ComplianceLevel
    confidence: Confidence
    description: str
    remediation: Optional[str] = None
    source_quote: Optional[str] = None  # Verbatim legal text from obligation engine
    gap_type: GapType = GapType.CODE  # default: code-level finding
    is_informational: bool = False  # True for coverage gaps, meta warnings — excluded from overall level

    def to_dict(self):
        d = asdict(self)
        d["level"] = self.level.value
        d["confidence"] = self.confidence.value
        # gap_type may be a GapType enum or a plain string (from detector.Finding interop)
        gt = self.gap_type
        d["gap_type"] = gt.value if hasattr(gt, "value") else (gt or GapType.CODE.value)
        return d


@dataclass
class ActionItem:
    """A single item in a compliance action plan."""
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    article: str
    action: str
    details: str
    effort: str = ""
    action_type: str = "automated"  # automated | human_judgment_required

    def to_dict(self):
        return asdict(self)


@dataclass
class ScanResult:
    """Unified scan result returned by all article modules."""
    article_number: int
    article_title: str
    project_path: str
    scan_date: str
    files_scanned: int
    language_detected: str
    overall_level: ComplianceLevel
    overall_confidence: Confidence
    findings: list[Finding] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    # AI attribution — which model assessed this project (set once, not per-finding)
    assessed_by: str = ""

    def to_dict(self):
        d = {
            "article_number": self.article_number,
            "article_title": self.article_title,
            "project_path": self.project_path,
            "scan_date": self.scan_date,
            "files_scanned": self.files_scanned,
            "language_detected": self.language_detected,
            "overall_level": self.overall_level.value,
            "overall_confidence": self.overall_confidence.value,
            "findings": [f.to_dict() for f in self.findings],
            "details": self.details,
        }
        if self.assessed_by:
            d["assessed_by"] = self.assessed_by
        return d

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, default=str)


@dataclass
class Explanation:
    """Unified explanation returned by all article modules."""
    article_number: int
    article_title: str
    one_sentence: str
    official_summary: str
    related_articles: dict[str, str]
    recital: str
    automation_summary: dict[str, list[str]]
    compliance_checklist_summary: str
    enforcement_date: str
    waiting_for: str

    def to_dict(self):
        return asdict(self)

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


@dataclass
class ActionPlan:
    """Unified action plan returned by all article modules."""
    article_number: int
    article_title: str
    project_path: str
    actions: list[ActionItem] = field(default_factory=list)
    disclaimer: str = ""

    def to_dict(self):
        return {
            "article_number": self.article_number,
            "article_title": self.article_title,
            "project_path": self.project_path,
            "total_actions": len(self.actions),
            "critical": sum(1 for a in self.actions if a.priority == "CRITICAL"),
            "high": sum(1 for a in self.actions if a.priority == "HIGH"),
            "medium": sum(1 for a in self.actions if a.priority == "MEDIUM"),
            "low": sum(1 for a in self.actions if a.priority == "LOW"),
            "actions": [a.to_dict() for a in self.actions],
            "disclaimer": self.disclaimer,
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


# ── Module Protocol ──

@runtime_checkable
class ArticleModule(Protocol):
    """Interface that every article module must implement."""

    @property
    def article_number(self) -> int: ...
    @property
    def article_title(self) -> str: ...
    @property
    def module_dir(self) -> str: ...

    def scan(self, project_path: str, context=None) -> ScanResult: ...
    def explain(self) -> Explanation: ...
    def action_plan(self, scan_result: ScanResult) -> ActionPlan: ...
    def compliance_checklist(self) -> dict: ...


# ── Cached File Index ──

@dataclass
class FileEntry:
    """A single file in the project index."""
    abs_path: str
    rel_path: str
    name_lower: str
    ext: str
    content: Optional[str] = None  # lazy-loaded
    _content_lower: Optional[str] = None
    _lines: Optional[list[str]] = None

    MAX_FILE_SIZE = 512 * 1024  # 512KB — truncate, never skip

    def read(self) -> str:
        """Read and cache file content.

        Large files (>512KB) are truncated to first 512KB, never skipped.
        A 600KB Python file could contain facial recognition code.
        Imports and key patterns are almost always in the first 512KB.

        No hardcoded skip lists — AI context decides what to skip.
        """
        if self.content is None:
            try:
                size = os.path.getsize(self.abs_path)
                with open(self.abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    if size > self.MAX_FILE_SIZE:
                        self.content = f.read(self.MAX_FILE_SIZE)
                    else:
                        self.content = f.read()
            except (OSError, PermissionError):
                self.content = ""
        return self.content

    def read_lower(self) -> str:
        """Return lowercased content (cached)."""
        if self._content_lower is None:
            self._content_lower = self.read().lower()
        return self._content_lower

    def lines(self) -> list[str]:
        """Return splitlines (cached)."""
        if self._lines is None:
            self._lines = self.read().splitlines()
        return self._lines


class ProjectIndex:
    """Indexes a project's files once for efficient repeated scanning.

    Walk the filesystem once, then all modules query the index.
    Excludes the compliancelint modules directory to prevent self-matching.
    """

    def __init__(self, project_path: str, exclude_dirs: set[str] | None = None):
        self.project_path = os.path.abspath(project_path)
        self._files: list[FileEntry] = []
        self._by_ext: dict[str, list[FileEntry]] = {}

        # Always exclude compliancelint modules from scanning
        _this_file = os.path.abspath(__file__)
        _core_dir = os.path.dirname(_this_file)
        _scanner_root = os.path.dirname(_core_dir)
        scanner_modules_dir = os.path.normcase(os.path.join(_scanner_root, "modules"))

        # AI context can override skip dirs via exclude_dirs parameter.
        # SKIP_DIRS is the FALLBACK — used when no AI context is available.
        skip = SKIP_DIRS | (exclude_dirs or set())

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in skip]

            # Skip our own modules directory (normcase for Windows case-insensitivity)
            abs_root = os.path.normcase(os.path.abspath(root))
            if abs_root == scanner_modules_dir or abs_root.startswith(scanner_modules_dir + os.sep):
                dirs.clear()
                continue

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, self.project_path)
                entry = FileEntry(
                    abs_path=abs_path,
                    rel_path=rel_path,
                    name_lower=fname.lower(),
                    ext=ext,
                )
                self._files.append(entry)
                self._by_ext.setdefault(ext, []).append(entry)

    def files(self, extensions: frozenset | set | None = None) -> list[FileEntry]:
        """Get files filtered by extension set."""
        if extensions is None:
            return self._files
        result = []
        for ext in extensions:
            result.extend(self._by_ext.get(ext, []))
        return result

    def source_files_for_compliance(self, extensions: frozenset | set | None = None) -> list[FileEntry]:
        """Get source files excluding only noise directories (benchmarks, fixtures, stubs).

        Compliance scanning needs to see production code, tests, docs, and examples —
        depth and accuracy take priority over speed. Only truly irrelevant directories
        (benchmarks, test fixtures, type stubs) are excluded.
        """
        candidates = self.files(extensions or SOURCE_EXTS)
        result = []
        for entry in candidates:
            parts = set(entry.rel_path.replace("\\", "/").lower().split("/"))
            if parts & SKIP_DIRS_COMPLIANCE:
                continue
            result.append(entry)
        return result

    def find_by_name(self, patterns: list[str],
                     extensions: frozenset | set | None = None) -> list[FileEntry]:
        """Find files whose names contain any of the patterns."""
        candidates = self.files(extensions)
        found = []
        for entry in candidates:
            for pattern in patterns:
                if pattern in entry.name_lower:
                    found.append(entry)
                    break
        return found

    def search_content(self, patterns: list[str],
                       extensions: frozenset | set | None = None,
                       use_regex: bool = False,
                       skip_comments: bool = True,
                       max_matches: int = 200) -> list[tuple[FileEntry, str, set[str]]]:
        """Search file content for patterns.

        Args:
            patterns: List of patterns to search for.
            extensions: File extensions to search (None = all).
            use_regex: If True, treat patterns as regex. If False, plain string match.
            skip_comments: If True, skip lines starting with comment prefixes.
            max_matches: Maximum number of file matches to return.

        Returns:
            List of (FileEntry, first_match_text, matched_patterns_set) tuples.
        """
        candidates = self.files(extensions)

        if use_regex:
            compiled = [(p, re.compile(p, re.IGNORECASE)) for p in patterns]
        else:
            patterns_lower = [p.lower() for p in patterns]

        results = []
        for entry in candidates:
            content = entry.read()
            if not content:
                continue

            matched = set()
            first_match_line = ""

            if use_regex:
                for p_str, p_re in compiled:
                    for line in entry.lines():
                        stripped = line.strip()
                        if skip_comments and stripped and any(
                            stripped.startswith(cp) for cp in _COMMENT_PREFIXES
                        ):
                            continue
                        m = p_re.search(line)
                        if m:
                            matched.add(p_str)
                            if not first_match_line:
                                first_match_line = stripped[:150]
                            break
            else:
                # Quick pre-check using cached lowercase content
                content_lower = entry.read_lower()
                if not any(p in content_lower for p in patterns_lower):
                    continue

                for line in entry.lines():
                    stripped = line.strip()
                    if skip_comments and stripped and any(
                        stripped.startswith(cp) for cp in _COMMENT_PREFIXES
                    ):
                        continue
                    line_lower = stripped.lower()
                    for p in patterns_lower:
                        if p in line_lower:
                            matched.add(p)
                            if not first_match_line:
                                first_match_line = stripped[:150]

            if matched:
                results.append((entry, first_match_line, matched))
                if len(results) >= max_matches:
                    break

        return results

    def search_regex(self, pattern: re.Pattern,
                     extensions: frozenset | set | None = None,
                     skip_comments: bool = True,
                     max_matches: int = 100) -> list[tuple[FileEntry, int, str]]:
        """Search file content with a compiled regex.

        Returns:
            List of (FileEntry, line_number, matched_text) tuples.
        """
        candidates = self.files(extensions)
        results = []
        for entry in candidates:
            content = entry.read()
            if not content:
                continue
            for line_num, line in enumerate(entry.lines(), 1):
                stripped = line.strip()
                if skip_comments and stripped and any(
                    stripped.startswith(cp) for cp in _COMMENT_PREFIXES
                ):
                    continue
                m = pattern.search(line)
                if m:
                    results.append((entry, line_num, m.group(0).strip()))
                    if len(results) >= max_matches:
                        return results
        return results

    @property
    def source_file_count(self) -> int:
        """Count of source code files."""
        return len(self.files(SOURCE_EXTS))


# ── Base class with common functionality ──

class BaseArticleModule:
    """Base class providing common utilities for article modules."""

    def __init__(self, module_dir: str, article_number: int, article_title: str):
        self._module_dir = module_dir
        self._article_number = article_number
        self._article_title = article_title

    @property
    def article_number(self) -> int:
        return self._article_number

    @property
    def article_title(self) -> str:
        return self._article_title

    @property
    def module_dir(self) -> str:
        return self._module_dir

    # ── JSON loaders ──

    def _load_json(self, filename: str) -> dict:
        """Load a JSON file from this module's directory."""
        filepath = os.path.join(self._module_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_obligations(self) -> dict:
        """Load the obligations JSON for this article."""
        obligations_dir = os.path.join(
            os.path.dirname(os.path.dirname(self._module_dir)),
            "obligations",
        )
        slug = os.path.basename(self._module_dir)
        filepath = os.path.join(obligations_dir, f"{slug}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_source(self) -> dict:
        """Load the official source text for this article."""
        sources_dir = os.path.join(
            os.path.dirname(os.path.dirname(self._module_dir)),
            "sources", "eu-ai-act",
        )
        filepath = os.path.join(sources_dir, f"article-{self._article_number}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def compliance_checklist(self) -> dict:
        """Load compliance checklist from JSON file."""
        return self._load_json("interim-standard.json")

    # ── Project scanning utilities ──

    # Class-level cache: build ProjectIndex once per project_path, share across all modules
    _index_cache: dict[str, "ProjectIndex"] = {}

    @classmethod
    def clear_index_cache(cls):
        """Clear the shared ProjectIndex cache."""
        cls._index_cache.clear()

    # ── AI-provided context ──
    _current_context = None  # Set before scan() is called

    @classmethod
    def set_context(cls, context):
        """Set AI-provided project context for the next scan."""
        cls._current_context = context

    @classmethod
    def get_context(cls):
        """Get the current AI-provided context, or None."""
        return cls._current_context

    # ── Config-aware context resolution ──
    _current_config = None  # Set before scan() is called

    @classmethod
    def set_config(cls, config):
        """Set user project config for the next scan."""
        cls._current_config = config

    @classmethod
    def get_config(cls):
        """Get the current project config, or None."""
        return cls._current_config

    def _effective_ctx(self, project_path: str = ""):
        """Return context with user config overrides applied.

        Priority: config overrides > AI context.
        When AI returns low confidence or "unclear", user config takes precedence.
        All article modules should call this instead of get_context() directly.
        """
        ctx = self.get_context()
        cfg = self.get_config()

        if ctx is None:
            raise RuntimeError(
                "AI context is required. Call cl_analyze_project() first, "
                "then pass your enriched context to the scan function."
            )

        if cfg is None:
            return ctx

        # Apply overrides — config values take precedence over AI values
        import copy
        ctx = copy.copy(ctx)

        if cfg.risk_classification_override:
            ctx.risk_classification = cfg.risk_classification_override
            ctx.risk_classification_confidence = "high"  # User-confirmed = high confidence
            if cfg.risk_classification_reasoning:
                ctx.risk_reasoning = f"[User override] {cfg.risk_classification_reasoning}"

        if cfg.primary_language_override:
            ctx.primary_language = cfg.primary_language_override

        if cfg.logging_framework_override:
            ctx.logging_framework = cfg.logging_framework_override
            ctx.logging_framework_confidence = "high"

        if cfg.monitoring_tools_override:
            ctx.monitoring_tools = cfg.monitoring_tools_override
            ctx.monitoring_tools_confidence = "high"

        return ctx

    # Articles that apply only to HIGH-RISK AI systems (Chapter III, Section 2)
    _HIGH_RISK_ONLY_ARTICLES = frozenset({9, 10, 11, 12, 13, 14, 15})

    # Articles that apply even to open-source systems (Art. 2(12) exceptions)
    _OPEN_SOURCE_APPLICABLE = frozenset({5, 50})

    # Risk classification strings that clearly mean "not high-risk"
    _NOT_HIGH_RISK_VALUES = frozenset({
        "not high-risk", "not_high_risk", "not high risk",
        "no", "not applicable", "n/a", "low-risk", "low risk",
        "minimal risk", "limited risk",
    })

    def _scope_gate(self, ctx, project_path: str) -> Optional["ScanResult"]:
        """Check universal scope exemptions from the AI-provided _scope answers.

        Returns NOT_APPLICABLE ScanResult (with legal citation) if the project
        is out of scope for this article. Returns None to proceed with scanning.

        Covers: Art. 2(1) territorial scope, Art. 2(3) military/defense,
        Art. 2(6) research-only, Art. 2(12) open-source exemption,
        Art. 3(1) AI system definition.
        """
        scope = ctx.get_article_answers("_scope") if ctx.compliance_answers else {}
        if not scope:
            return None  # No scope info — proceed with scan

        obl_prefix = f"ART{self._article_number:02d}"
        lang = ctx.primary_language or "unknown"

        # ── Art. 3(1): Not an AI system ──
        if scope.get("is_ai_system") is False:
            reasoning = scope.get("is_ai_system_reasoning", "")
            return self._not_applicable_result(
                project_path, lang, obl_prefix,
                legal_basis="Art. 3(1)",
                reason=(
                    f"This project is not an AI system as defined by Art. 3(1) of the "
                    f"EU AI Act ('a machine-based system that is designed to operate with "
                    f"varying levels of autonomy and that may exhibit adaptiveness after "
                    f"deployment and that, for explicit or implicit objectives, infers, "
                    f"from the input it receives, how to generate outputs'). "
                    f"Reasoning: {reasoning or 'AI determined this is not an AI system'}."
                ),
            )

        # ── Art. 2(1): Territorial scope ──
        if scope.get("territorial_scope_applies") is False:
            reasoning = scope.get("territorial_scope_reasoning", "")
            return self._not_applicable_result(
                project_path, lang, obl_prefix,
                legal_basis="Art. 2(1)",
                reason=(
                    f"The EU AI Act does not apply to this system. Art. 2(1) requires "
                    f"the provider to place the system on the market or put it into "
                    f"service in the EU, or the deployer to be in the EU, or the output "
                    f"to be used in the EU. "
                    f"Reasoning: {reasoning or 'none provided'}."
                ),
            )

        # ── Art. 2(3): Military/defense ──
        if scope.get("is_military_defense") is True:
            return self._not_applicable_result(
                project_path, lang, obl_prefix,
                legal_basis="Art. 2(3)",
                reason=(
                    "This AI system is developed or used exclusively for military or "
                    "defense purposes. Art. 2(3) excludes AI systems placed on the market, "
                    "put into service, or used exclusively for military purposes from "
                    "the scope of the EU AI Act."
                ),
            )

        # ── Art. 2(6): Research only ──
        if scope.get("is_research_only") is True:
            return self._not_applicable_result(
                project_path, lang, obl_prefix,
                legal_basis="Art. 2(6)",
                reason=(
                    "This AI system is used exclusively for scientific research and "
                    "development and has not been placed on the market or put into "
                    "service. Art. 2(6) excludes AI systems used solely for R&D "
                    "purposes before market placement."
                ),
            )

        # ── Art. 2(12): Open-source exemption ──
        if scope.get("is_open_source") is True:
            if self._article_number not in self._OPEN_SOURCE_APPLICABLE:
                license_name = scope.get("open_source_license", "unknown")
                return self._not_applicable_result(
                    project_path, lang, obl_prefix,
                    legal_basis="Art. 2(12)",
                    reason=(
                        f"This is an open-source AI component (license: {license_name}). "
                        f"Art. 2(12) exempts providers of free and open-source AI "
                        f"components from Title III obligations (Art. 6-15), UNLESS the "
                        f"system is used for prohibited practices (Art. 5) or has "
                        f"transparency obligations (Art. 50). Art. {self._article_number} "
                        f"is a Title III obligation and does not apply to this open-source "
                        f"component. Note: this exemption does NOT apply if the open-source "
                        f"component is incorporated into a high-risk AI system by a deployer "
                        f"— in that case, the deployer's obligations under Art. 25-26 apply."
                    ),
                )

        return None  # All scope checks passed — proceed with scan

    def _not_applicable_result(
        self, project_path: str, language: str, obl_prefix: str,
        legal_basis: str, reason: str,
    ) -> "ScanResult":
        """Create a NOT_APPLICABLE ScanResult with legal citation."""
        return ScanResult(
            article_number=self._article_number,
            article_title=self._article_title,
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=0,
            language_detected=language,
            overall_level=ComplianceLevel.NOT_APPLICABLE,
            overall_confidence=Confidence.HIGH,
            findings=[Finding(
                obligation_id=f"{obl_prefix}-NOT-APPLICABLE",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.HIGH,
                description=(
                    f"[{legal_basis}] Art. {self._article_number} "
                    f"({self._article_title}) does not apply. {reason}"
                ),
                remediation=(
                    "If this scope determination is incorrect, override in "
                    "the _scope section of compliance_answers."
                ),
            )],
            details={
                "skip_reason": "scope_exemption",
                "legal_basis": legal_basis,
            },
        )

    def _high_risk_only_check(self, ctx, project_path: str) -> Optional["ScanResult"]:
        """Return NOT_APPLICABLE ScanResult if project is confirmed not-high-risk.

        Call at the start of scan() for Art. 9-15 only. These articles apply
        exclusively to high-risk AI systems. If the AI has classified this
        project as not-high-risk with medium/high confidence, skip the scan.

        Returns:
            ScanResult with NOT_APPLICABLE if skipping, else None (continue scanning).
        """
        if self._article_number not in self._HIGH_RISK_ONLY_ARTICLES:
            return None  # This article applies to all systems

        risk = (ctx.risk_classification or "").lower().strip()
        conf = (ctx.risk_classification_confidence or "").lower().strip()

        if risk not in self._NOT_HIGH_RISK_VALUES:
            return None  # Unknown or high-risk classification — proceed with scan

        if conf not in ("high", "medium"):
            return None  # Low confidence — scan anyway, warn user

        # Confirmed not-high-risk with medium/high confidence → NOT_APPLICABLE
        obl_prefix = f"ART{self._article_number:02d}"
        return ScanResult(
            article_number=self._article_number,
            article_title=self._article_title,
            project_path=project_path,
            scan_date=datetime.now(timezone.utc).isoformat(),
            files_scanned=0,
            language_detected=ctx.primary_language or "unknown",
            overall_level=ComplianceLevel.NOT_APPLICABLE,
            overall_confidence=Confidence.HIGH,
            findings=[Finding(
                obligation_id=f"{obl_prefix}-NOT-APPLICABLE",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.NOT_APPLICABLE,
                confidence=Confidence.HIGH,
                description=(
                    f"Art. {self._article_number} ({self._article_title}) applies only to "
                    f"high-risk AI systems (EU AI Act Chapter III, Section 2). "
                    f"AI classification: '{ctx.risk_classification}' "
                    f"(confidence: {ctx.risk_classification_confidence}). "
                    f"Reasoning: {ctx.risk_reasoning or 'none provided'}. "
                    "This article scan is skipped."
                ),
                remediation=(
                    "If this classification is incorrect, add to .compliancelintrc: "
                    '{"risk_classification_override": "likely high-risk", '
                    '"risk_classification_reasoning": "explain why"}'
                ),
            )],
            details={
                "skip_reason": "not_high_risk_system",
                "risk_classification": ctx.risk_classification,
                "risk_classification_confidence": ctx.risk_classification_confidence,
                "risk_reasoning": ctx.risk_reasoning or "",
            },
        )

    def _ctx_warnings(self, ctx) -> list:
        """Return warning findings for low-confidence or unclear AI classifications.

        Call this in each module's scan() and prepend warnings to findings.
        Applies to ALL articles — this is the universal confidence layer.
        """
        warnings = []

        risk = (ctx.risk_classification or "").lower()
        conf = (ctx.risk_classification_confidence or "").lower()

        if risk == "unclear":
            warnings.append(Finding(
                obligation_id="META-WARN-1",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    "⚠️ Risk classification is UNCLEAR. AI could not determine whether "
                    "this project is a high-risk AI system under EU AI Act Annex III. "
                    f"Reasoning: {ctx.risk_reasoning or 'none provided'}. "
                    "Scanner assumed non-high-risk behavior for biometric obligations — "
                    "results may be incomplete."
                ),
                remediation=(
                    "Add 'risk_classification_override' to .compliancelintrc with value "
                    "'likely high-risk' or 'not high-risk', and explain your reasoning in "
                    "'risk_classification_reasoning'. Example: "
                    '{"risk_classification_override": "not high-risk", '
                    '"risk_classification_reasoning": "CRUD app, no AI decision-making"}'
                ),
                is_informational=True,
            ))
        elif conf == "low":
            warnings.append(Finding(
                obligation_id="META-WARN-2",
                file_path="project-wide",
                line_number=None,
                level=ComplianceLevel.UNABLE_TO_DETERMINE,
                confidence=Confidence.LOW,
                description=(
                    f"⚠️ Risk classification confidence is LOW: '{ctx.risk_classification}'. "
                    f"Reasoning: {ctx.risk_reasoning or 'none provided'}."
                ),
                remediation=(
                    "Confirm or override in .compliancelintrc: "
                    '{"risk_classification_override": "not high-risk"}'
                ),
                is_informational=True,
            ))

        return warnings

    def _build_index(self, project_path: str) -> ProjectIndex:
        """Build a file index for the project (walk once, query many times).

        Uses a class-level cache so that when multiple modules scan the same
        project, the filesystem is only walked once.
        """
        abs_path = os.path.abspath(project_path)
        if abs_path not in BaseArticleModule._index_cache:
            BaseArticleModule._index_cache[abs_path] = ProjectIndex(abs_path)
        return BaseArticleModule._index_cache[abs_path]

    def _detect_language(self, project_path: str) -> str:
        """Detect the primary language of a project.

        Priority: AI context > user config override > file-count heuristic.
        The heuristic is a last resort — use AI context whenever available.
        """
        ctx = self.get_context()
        cfg = self.get_config()

        # 1. User config override (highest priority)
        if cfg and cfg.primary_language_override:
            return cfg.primary_language_override.lower()

        # 2. AI context (high confidence preferred)
        if ctx and ctx.primary_language:
            conf = (ctx.language_confidence if hasattr(ctx, "language_confidence") else "")
            if conf != "low":
                return ctx.primary_language.lower()

        # 3. File-count heuristic (fallback — least accurate)
        index = self._build_index(project_path)
        counts = {"python": 0, "javascript": 0, "typescript": 0,
                  "java": 0, "go": 0, "rust": 0, "csharp": 0}
        lang_map = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".mjs": "javascript", ".cjs": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".java": "java", ".go": "go", ".rs": "rust",
            ".cs": "csharp",
        }
        for entry in index.files(SOURCE_EXTS):
            lang = lang_map.get(entry.ext)
            if lang:
                counts[lang] += 1
        if not any(counts.values()):
            return "unknown"
        return max(counts, key=counts.get)

    def _detect_languages(self, project_path: str) -> list[str]:
        """Detect ALL languages in a project, ordered by file count.

        Returns list of language names, e.g. ["go", "javascript", "typescript"].
        For monorepo support -- scan all languages, not just the primary one.
        """
        index = self._build_index(project_path)
        counts = {"python": 0, "javascript": 0, "typescript": 0,
                  "java": 0, "go": 0, "rust": 0, "csharp": 0}
        lang_map = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".mjs": "javascript", ".cjs": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".java": "java", ".go": "go", ".rs": "rust",
            ".cs": "csharp",
        }
        for entry in index.files(SOURCE_EXTS):
            lang = lang_map.get(entry.ext)
            if lang:
                counts[lang] += 1
        # Return languages with > 0 files, sorted by count descending
        return [lang for lang, count in sorted(counts.items(), key=lambda x: -x[1]) if count > 0]

    def _count_source_files(self, project_path: str) -> int:
        """Count source code files in a project."""
        return ProjectIndex(project_path).source_file_count

    # ── Pattern matching utilities ──

    def _search_patterns(self, index: ProjectIndex, patterns: list[str],
                         extensions: frozenset | set | None = None,
                         use_regex: bool = False,
                         skip_comments: bool = True,
                         ) -> tuple[bool, str, set[str]]:
        """Search project for patterns using the index.

        Returns:
            (found: bool, first_match_relpath: str, matched_patterns: set)
        """
        if extensions is None:
            extensions = SOURCE_EXTS | CONFIG_EXTS

        results = index.search_content(
            patterns, extensions=extensions,
            use_regex=use_regex, skip_comments=skip_comments,
            max_matches=1,
        )

        if results:
            all_matched = set()
            first_file = "project-wide"
            for entry, _, matched in results:
                all_matched |= matched
                if first_file == "project-wide":
                    first_file = entry.rel_path

            # Re-search to get ALL matched patterns (first search stopped at 1 file)
            all_results = index.search_content(
                patterns, extensions=extensions,
                use_regex=use_regex, skip_comments=skip_comments,
            )
            all_matched = set()
            for _, _, matched in all_results:
                all_matched |= matched

            return True, first_file, all_matched

        return False, "project-wide", set()

    def _find_files(self, index: ProjectIndex, name_patterns: list[str],
                    extensions: frozenset | set | None = None) -> list[str]:
        """Find files by name pattern using the index.

        Returns list of relative paths.
        """
        entries = index.find_by_name(
            [p.lower() for p in name_patterns],
            extensions=extensions,
        )
        return [e.rel_path for e in entries]

    # ── Finding management ──

    MAX_FINDINGS_PER_OBLIGATION = 10  # Cap per obligation_id to prevent noise

    _PROCESS_DISCLAIMER = (
        " [PROCESS FINDING: This finding is based on file/document detection, "
        "not code analysis. Document existence does not equal obligation fulfillment — "
        "a human reviewer must verify content adequacy.]"
    )

    def _apply_process_disclaimers(self, findings: list[Finding]) -> list[Finding]:
        """Append standardized disclaimer to all PROCESS-type findings.

        PROCESS findings detect file existence, not content adequacy.
        Without a disclaimer, users may mistake a README for a valid risk assessment.
        """
        for f in findings:
            if f.gap_type == GapType.PROCESS and self._PROCESS_DISCLAIMER not in f.description:
                f.description = f.description + self._PROCESS_DISCLAIMER
        return findings

    def _cap_findings(self, findings: list[Finding]) -> list[Finding]:
        """Cap findings per obligation_id to prevent output explosion.

        When a module generates 500+ "endpoint has no logging" findings,
        keep only the first N per obligation_id and add a summary finding.
        """
        from collections import defaultdict, Counter

        cap = self.MAX_FINDINGS_PER_OBLIGATION
        counts = Counter(f.obligation_id for f in findings)

        # If no obligation exceeds the cap, return as-is
        if all(c <= cap for c in counts.values()):
            return findings

        # Group by obligation_id, keep first N, add summary for rest
        groups = defaultdict(list)
        for f in findings:
            groups[f.obligation_id].append(f)

        result = []
        for obl_id, group in groups.items():
            if len(group) <= cap:
                result.extend(group)
            else:
                result.extend(group[:cap])
                # Add a summary finding for the rest
                extra = len(group) - cap
                # Use the level of the majority
                levels = [f.level for f in group]
                majority_level = max(set(levels), key=levels.count)
                result.append(Finding(
                    obligation_id=obl_id,
                    file_path="project-wide",
                    line_number=None,
                    level=majority_level,
                    confidence=Confidence.MEDIUM,
                    description=(
                        f"... and {extra} more similar findings for this obligation "
                        f"(total: {len(group)})."
                    ),
                ))

        return result

    # ── AI-answer → Finding mapping helper ──

    def _finding_from_answer(
        self,
        obligation_id: str,
        answer,                        # bool | None — from compliance_answers
        true_description: str,
        false_description: str,
        none_description: str = "AI could not determine this from the available project information.",
        true_level: "ComplianceLevel" = None,
        evidence: list = None,
        gap_type: "GapType" = None,
        file_path: str = "project-wide",
    ) -> "Finding":
        """Map a boolean AI answer to a Finding.

        answer=True  → true_level (default PARTIAL) with true_description
        answer=False → NON_COMPLIANT with false_description
        answer=None  → UNABLE_TO_DETERMINE with none_description

        PARTIAL is used instead of COMPLIANT because AI-detected evidence
        always requires human verification before final sign-off.

        AI model attribution is stored once in ScanResult.assessed_by,
        not repeated in every finding description.
        """
        if true_level is None:
            true_level = ComplianceLevel.PARTIAL

        if answer is True:
            level = true_level
            desc = true_description
            if evidence:
                desc += f" Evidence: {'; '.join(str(e) for e in evidence[:3])}"
            confidence = Confidence.MEDIUM
        elif answer is False:
            level = ComplianceLevel.NON_COMPLIANT
            desc = false_description
            confidence = Confidence.MEDIUM
        else:
            level = ComplianceLevel.UNABLE_TO_DETERMINE
            desc = none_description
            confidence = Confidence.LOW

        return Finding(
            obligation_id=obligation_id,
            file_path=file_path,
            line_number=None,
            level=level,
            confidence=confidence,
            description=desc,
            gap_type=gap_type or GapType.PROCESS,
        )

    # ── Compliance computation ──

    def _compute_overall_level(self, findings: list[Finding]) -> ComplianceLevel:
        """Compute overall compliance from individual findings.

        Excludes informational findings (coverage gaps, META-WARN) from the
        overall level calculation. These are informational — they indicate
        obligations not yet checked, not compliance failures.
        """
        # Filter out informational findings (coverage gaps, warnings)
        substantive = [f for f in findings if not f.is_informational]
        levels = [f.level for f in substantive]
        if not levels:
            return ComplianceLevel.UNABLE_TO_DETERMINE
        # Exclude NOT_APPLICABLE from the judgment (they don't affect compliance)
        active = [l for l in levels if l != ComplianceLevel.NOT_APPLICABLE]
        if not active:
            # All substantive findings are NOT_APPLICABLE
            return ComplianceLevel.NOT_APPLICABLE
        if all(l == ComplianceLevel.COMPLIANT for l in active):
            return ComplianceLevel.COMPLIANT
        if any(l == ComplianceLevel.NON_COMPLIANT for l in active):
            return ComplianceLevel.NON_COMPLIANT
        if any(l == ComplianceLevel.PARTIAL for l in active):
            return ComplianceLevel.PARTIAL
        return ComplianceLevel.UNABLE_TO_DETERMINE
