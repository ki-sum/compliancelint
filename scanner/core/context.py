"""
AI-First Project Context — the bridge between AI understanding and rule-based scanning.

Architecture principle: AI is the eyes, Scanner is the rule engine.

The AI client (Claude in MCP mode) reads the project and fills
in two things:
  1. ProjectStructure — what kind of project this is, what files exist
  2. ComplianceAnswers — per-article answers to specific compliance questions

The scanner modules receive this context and do ONLY obligation mapping:
  AI answer → legal obligation → Finding (COMPLIANT / NON_COMPLIANT / UNABLE_TO_DETERMINE)

There is NO regex detection in scanner modules. Detection is 100% the AI's job.
This means the scanner works for any language, any encoding, any naming convention.

Note: ComplianceLint is MCP-only. There is no CLI or offline mode.

There is NO offline fallback. AI is required.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


# Fields that must be lists (never strings) per article — used by get_article_answers()
_LIST_FIELDS: dict = {
    "art5":  ["prohibited_practices"],
    "art6":  ["annex_iii_categories"],
    "art9":  ["risk_doc_paths", "testing_evidence", "risk_code_evidence", "metrics_evidence"],
    "art10": ["data_doc_paths", "bias_evidence"],
    "art11": ["doc_paths", "documented_aspects"],
    "art12": ["logging_evidence"],
    "art13": ["explainability_evidence", "transparency_paths"],
    "art14": ["oversight_evidence", "override_evidence"],
    "art15": ["accuracy_evidence", "robustness_evidence"],
    "art50": ["disclosure_evidence", "emotion_biometric_evidence", "deep_fake_evidence"],
}

# Fields that must be bool or None (never strings like "true")
_BOOL_FIELDS: dict = {
    "art5":  ["is_realtime_processing"],
    "art6":  ["is_high_risk"],
    "art9":  ["has_risk_docs", "has_testing_infrastructure", "has_risk_code_patterns", "has_defined_metrics", "affects_children"],
    "art10": ["has_data_governance_doc", "has_bias_mitigation", "has_data_lineage", "processes_special_category_data"],
    "art11": ["has_technical_docs", "is_annex_i_product"],
    "art12": ["has_logging", "has_retention_config"],
    "art13": ["has_explainability", "has_transparency_info"],
    "art14": ["has_human_oversight", "has_override_mechanism"],
    "art15": ["has_accuracy_testing", "has_robustness_testing", "has_fallback_behavior", "continues_learning_after_deployment"],
    "art50": ["is_chatbot_or_interactive_ai", "is_generating_synthetic_content",
              "has_ai_disclosure_to_users", "has_content_watermarking",
              "is_emotion_recognition_system", "is_biometric_categorization_system",
              "has_emotion_biometric_disclosure", "is_deep_fake_system",
              "has_deep_fake_disclosure"],
    "_scope": ["is_ai_system", "territorial_scope_applies", "is_open_source",
               "is_military_defense", "is_research_only",
               "is_biometric_system", "is_financial_institution"],
}


@dataclass
class ProjectContext:
    """AI-provided understanding of a project.

    The AI fills this in after reading project files.
    The scanner uses this instead of hardcoded assumptions.

    compliance_answers is the key new field: per-article answers to compliance
    questions. Each article reads its own sub-dict from here.

    Schema for compliance_answers:
    {
      "art5": {
        "is_realtime_processing": true | false | null,  # does the system process data in real-time vs batch?
        "processing_mode_evidence": "description of why (e.g. streaming API calls, live camera feed, batch job)",
        "prohibited_practices": [
          {
            "practice": "biometric_surveillance" | "social_scoring" |
                        "subliminal_manipulation" | "prohibited_emotion_recognition" |
                        "prohibited_real_time_biometrics",
            "detected": true | false | null,  # null = AI could not determine
            "evidence": "description of what was found, or empty string",
            "evidence_paths": ["file:line", ...],
            "confidence": "high" | "medium" | "low"
          }
        ]
      },
      "art6": {
        "annex_iii_categories": ["Biometrics", "Employment", ...],  # detected categories
        "annex_i_product_type": null | "Medical device" | ...,
        "is_high_risk": true | false | null,
        "reasoning": "one sentence explanation"
      },
      "art9": {
        "has_risk_docs": true | false | null,
        "risk_doc_paths": ["docs/risk_assessment.md", ...],
        "has_testing_infrastructure": true | false | null,
        "testing_evidence": ["tests/", "benchmarks/", ...],
        "has_risk_code_patterns": true | false | null,
        "risk_code_evidence": ["description of what was found"]
      },
      "art10": {
        "has_data_governance_doc": true | false | null,
        "data_doc_paths": ["docs/data_sheet.md", ...],
        "has_bias_mitigation": true | false | null,
        "bias_evidence": ["description"],
        "has_data_lineage": true | false | null
      },
      "art11": {
        "has_technical_docs": true | false | null,
        "doc_paths": ["docs/architecture.md", ...],
        "documented_aspects": ["model architecture", "training data", "performance metrics", ...]
      },
      "art12": {
        "has_logging": true | false | null,
        "logging_description": "e.g. uses structlog with JSON output",
        "logging_evidence": ["src/logging_config.py:5", ...],
        "has_retention_config": true | false | null,
        "retention_days": null | 180 | 365,
        "retention_evidence": "description of where retention is configured"
      },
      "art13": {
        "has_explainability": true | false | null,
        "explainability_evidence": ["description"],
        "has_transparency_info": true | false | null,
        "transparency_paths": ["docs/model_card.md", ...]
      },
      "art14": {
        "has_human_oversight": true | false | null,
        "oversight_evidence": ["description of approval flow, review gates, etc."],
        "has_override_mechanism": true | false | null,
        "override_evidence": ["description"]
      },
      "art15": {
        "has_accuracy_testing": true | false | null,
        "accuracy_evidence": ["tests/test_accuracy.py", ...],
        "has_robustness_testing": true | false | null,
        "robustness_evidence": ["description"],
        "has_fallback_behavior": true | false | null
      },
      "art50": {
        "is_chatbot_or_interactive_ai": true | false | null,
        "is_generating_synthetic_content": true | false | null,
        "has_ai_disclosure_to_users": true | false | null,
        "disclosure_evidence": ["description"],
        "has_content_watermarking": true | false | null
      }
    }
    """

    # ── Project identity ──
    primary_language: str = ""           # e.g. "python", "typescript", "java"
    language_confidence: str = ""        # "high" | "medium" | "low"
    languages: list = field(default_factory=list)  # all languages found
    framework: str = ""                  # e.g. "Next.js 14", "FastAPI", "Spring Boot"
    project_type: str = ""               # e.g. "web app", "ML training pipeline", "CLI tool"

    # ── AI classification ──
    risk_classification: str = ""        # AI's assessment: "likely high-risk", "not high-risk", "unclear"
    risk_reasoning: str = ""             # Why the AI thinks so
    risk_classification_confidence: str = ""  # "high" | "medium" | "low"
    ai_libraries: list = field(default_factory=list)  # e.g. ["openai", "transformers"]

    # ── File classification (AI decides, not hardcoded) ──
    source_dirs: list = field(default_factory=list)
    test_dirs: list = field(default_factory=list)
    generated_files: list = field(default_factory=list)
    config_files: list = field(default_factory=list)
    doc_files: list = field(default_factory=list)

    # ── Infrastructure (AI identifies, not hardcoded lists) ──
    logging_framework: str = ""
    logging_framework_confidence: str = ""
    logging_config_file: str = ""
    monitoring_tools: list = field(default_factory=list)
    monitoring_tools_confidence: str = ""
    monitoring_files: list = field(default_factory=list)
    test_framework: str = ""

    # ── AI attribution (audit trail) ──
    # Which AI model assessed this project. Appended to every finding description
    # so reviewers know whether to trust the result or re-run with a better model.
    # Format: "claude-opus-4-6", "gpt-4o", "mistral-large-latest", etc.
    # Set by the AI client in compliance_answers.
    ai_model: str = ""

    # ── Per-article compliance answers (THE KEY NEW FIELD) ──
    # AI reads source code and answers compliance questions per article.
    # Scanner modules read from here instead of running their own detection.
    compliance_answers: dict = field(default_factory=dict)



    # ── AI disambiguation cache ──
    disambiguations: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectContext":
        """Create from dict, ignoring unknown keys for forward compatibility.

        Smart detection: if top-level keys look like article answers (e.g., "art12"),
        auto-wrap them into compliance_answers. This handles the common case where
        users pass {"art12": {...}} instead of {"compliance_answers": {"art12": {...}}}.
        """
        known_fields = {f for f in cls.__dataclass_fields__}

        # Check if user passed article answers at top level instead of nested
        article_keys = {k for k in data if k.startswith("art") or k.startswith("_scope") or k.startswith("_scan")}
        non_field_articles = article_keys - known_fields
        if non_field_articles and "compliance_answers" not in data:
            # User passed {"art12": {...}} directly — wrap into compliance_answers
            compliance = {}
            other = {}
            for k, v in data.items():
                if k.startswith("art") or k.startswith("_scope") or k.startswith("_scan"):
                    compliance[k] = v
                else:
                    other[k] = v
            other["compliance_answers"] = compliance
            data = other

        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "ProjectContext":
        return cls.from_dict(json.loads(json_str))

    @property
    def is_empty(self) -> bool:
        """Check if this context has been populated by AI."""
        return not self.primary_language and not self.compliance_answers

    def get_article_answers(self, article_key: str) -> dict:
        """Get compliance answers for a specific article, with type coercion.

        Coerces common AI output errors:
          - List fields that are strings → wrapped in a list
          - Bool fields that are "true"/"false" strings → proper bool
          - Bool fields that are 1/0 integers → proper bool

        Args:
            article_key: e.g. "art9", "art12", "art50"

        Returns:
            dict of answers (type-safe), empty dict if not provided.
        """
        raw = self.compliance_answers.get(article_key, {})
        if not raw:
            return raw
        result = dict(raw)

        # Coerce list fields
        for field in _LIST_FIELDS.get(article_key, []):
            if field in result and not isinstance(result[field], list):
                val = result[field]
                result[field] = [val] if val else []

        # Coerce bool fields: string → bool/None, int → bool
        for field in _BOOL_FIELDS.get(article_key, []):
            if field in result:
                val = result[field]
                if isinstance(val, str):
                    low = val.lower().strip()
                    if low in ("true", "yes", "1"):
                        result[field] = True
                    elif low in ("false", "no", "0"):
                        result[field] = False
                    elif low in ("null", "none", ""):
                        result[field] = None
                elif isinstance(val, int) and not isinstance(val, bool):
                    result[field] = bool(val)

        return result


def _build_scanning_strategy() -> dict:
    """Build per-article scanning guidance from obligation JSONs.

    Dynamically reads detection_method and what_to_scan from each
    obligation JSON. Zero hardcoded search terms — the obligation
    JSONs are the single source of truth.
    """
    import json as _json

    obligations_dir = os.path.join(os.path.dirname(__file__), "..", "obligations")
    if not os.path.isdir(obligations_dir):
        return {"error": "obligations directory not found"}

    per_article = {}
    for fname in sorted(os.listdir(obligations_dir)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(obligations_dir, fname), "r", encoding="utf-8") as f:
                data = _json.load(f)
        except (ValueError, OSError):
            continue

        meta = data.get("_metadata", {})
        art_num = meta.get("article")
        title = meta.get("title", "")
        if not art_num:
            continue

        # Extract unique detection methods and scan targets
        methods = []
        scan_targets = set()
        for obl in data.get("obligations", []):
            auto = obl.get("automation_assessment", {})
            method = auto.get("detection_method", "")
            if method and method != "N/A" and "permission" not in method.lower():
                methods.append(method)
            for target in auto.get("what_to_scan", []):
                scan_targets.add(target)

        if methods:
            per_article[f"art{art_num}"] = {
                "title": title,
                "what_to_scan": sorted(scan_targets),
                "detection_hints": methods[:5],  # cap at 5 to avoid bloat
            }

    return {
        "instruction": (
            "For each article below, use Grep to search the ENTIRE codebase "
            "for relevant patterns based on the detection_hints. Then Read only "
            "the files that match. Use your knowledge of the project's language "
            "and framework to choose appropriate search terms — the hints describe "
            "WHAT to look for, not the exact regex. "
            "Report progress to the user every ~20 files read."
        ),
        "articles": per_article,
    }


def analyze_project_metadata(project_path: str) -> dict:
    """Collect project metadata for AI to analyze.

    This function reads metadata files and samples source code.
    Designed to give the AI enough to answer both structural AND compliance questions.

    The AI client should:
    1. Call this function to get metadata + source samples
    2. Read the project files listed in the metadata
    3. Fill in ProjectContext including compliance_answers
    4. Pass the context to the scanner

    Returns a dict with project metadata + source code samples.
    """
    project_path = os.path.abspath(project_path)

    _SKIP_DIRS = frozenset({
        'node_modules', '__pycache__', '.git', 'venv', '.venv',
        'target', 'build', 'dist', '.next', '.nuxt', 'site-packages',
    })

    # ── 1. Directory tree (top 2 levels) ──
    top_dirs = []
    top_files = []
    for item in sorted(os.listdir(project_path)):
        full = os.path.join(project_path, item)
        if os.path.isdir(full):
            if item.startswith('.') and item not in ('.github', '.vscode'):
                continue
            if item in _SKIP_DIRS:
                top_dirs.append(f"{item}/ (skipped)")
                continue
            try:
                children = os.listdir(full)
                child_dirs = [c for c in children if os.path.isdir(os.path.join(full, c))]
                child_files = [c for c in children if os.path.isfile(os.path.join(full, c))]
                top_dirs.append(f"{item}/ ({len(child_dirs)} dirs, {len(child_files)} files)")
            except PermissionError:
                top_dirs.append(f"{item}/ (no access)")
        elif os.path.isfile(full):
            top_files.append(item)

    # ── 2. File type counts ──
    ext_counts = {}
    total_files = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                total_files += 1

    sorted_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:15]

    # ── 3. Read manifest/config files ──
    config_contents = {}
    manifest_files = [
        'package.json', 'requirements.txt', 'pyproject.toml', 'setup.py', 'setup.cfg',
        'Pipfile', 'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
        'build.gradle.kts', 'composer.json', 'Gemfile', '*.csproj',
    ]

    for mf in manifest_files:
        if mf.startswith('*'):
            import glob
            matches = glob.glob(os.path.join(project_path, mf))
            if not matches:
                matches = glob.glob(os.path.join(project_path, '*', mf))
            for match in matches[:1]:
                rel = os.path.relpath(match, project_path)
                try:
                    with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                        config_contents[rel] = f.read(3000)
                except (OSError, PermissionError):
                    pass
        else:
            fpath = os.path.join(project_path, mf)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        config_contents[mf] = f.read(3000)
                except (OSError, PermissionError):
                    pass
            else:
                import glob
                matches = glob.glob(os.path.join(project_path, '*', mf))
                for match in matches[:2]:
                    rel = os.path.relpath(match, project_path)
                    try:
                        with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                            config_contents[rel] = f.read(3000)
                    except (OSError, PermissionError):
                        pass

    # ── 4. README snippet ──
    readme_snippet = ""
    for readme_name in ['README.md', 'README.rst', 'README.txt', 'README']:
        rpath = os.path.join(project_path, readme_name)
        if os.path.isfile(rpath):
            try:
                with open(rpath, 'r', encoding='utf-8', errors='ignore') as f:
                    readme_snippet = f.read(500)
            except (OSError, PermissionError):
                pass
            break

    # ── 5. Sample source files (key for compliance detection) ──
    # AI needs to see actual code to answer compliance questions.
    # Sample up to 5 source files, 2KB each.
    source_samples = {}
    source_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cs', '.rb', '.php'}
    sample_count = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            if sample_count >= 5:
                break
            ext = os.path.splitext(fname)[1].lower()
            if ext in source_exts:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, project_path)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        source_samples[rel] = f.read(2000)
                    sample_count += 1
                except (OSError, PermissionError):
                    pass
        if sample_count >= 5:
            break

    # ── 6. CI/CD detection ──
    ci_configs = []
    for cp in ['.github/workflows', '.gitlab-ci.yml', '.circleci/config.yml',
               'Jenkinsfile', '.travis.yml', 'azure-pipelines.yml']:
        if os.path.exists(os.path.join(project_path, cp)):
            ci_configs.append(cp)

    # ── 7. Scanning strategy (dynamic from obligation JSONs) ──
    scanning_strategy = _build_scanning_strategy()

    return {
        "project_path": project_path,
        "directory_tree": {"directories": top_dirs, "root_files": top_files},
        "file_types": dict(sorted_exts),
        "total_files": total_files,
        "config_contents": config_contents,
        "readme_snippet": readme_snippet,
        "source_samples": source_samples,
        "ci_configs": ci_configs,
        "scanning_strategy": scanning_strategy,
    }


# ── compliance_answers Schema Reference ──
#
# ComplianceLint is MCP-only. There is no CLI or API-based mode.
# In MCP mode, the AI (Claude) reads the full codebase directly using its own
# file-reading tools, then fills in compliance_answers following this schema.
#
# This constant serves as the canonical schema reference and is used in:
#   - cl_analyze_project() docstring (tells Claude what to fill in)
#   - Tests (as the ground-truth schema)
#   - Documentation generation
#
# It is NOT sent as an API prompt. Claude reads it as part of the tool definition.

COMPLIANCE_ANSWERS_SCHEMA = """You are analyzing a software project for EU AI Act compliance scanning.

Your job: read the project metadata and source samples below, then fill in a JSON object
that the compliance scanner will use. The scanner does NO detection of its own — it relies
entirely on YOUR answers to check compliance.

CRITICAL — CONFIDENCE AND COMPLETENESS RULES:
  - "confidence": "high"   → you have read ALL relevant files and are certain
  - "confidence": "medium" → you have read the relevant files but some ambiguity remains
  - "confidence": "low"    → you have NOT read enough files to be certain
  - null (for boolean fields) → you cannot determine this from the available information

PROJECT METADATA:
{metadata}

Respond with ONLY a JSON object (no markdown, no explanation) with this structure:

{{
  "ai_model": "your model identifier, e.g. claude-opus-4-6 or gpt-4o",
  "primary_language": "main programming language",
  "language_confidence": "high | medium | low",
  "languages": ["all languages found"],
  "framework": "web/app framework used",
  "project_type": "what kind of project this is",
  "risk_classification": "likely high-risk | not high-risk | unclear",
  "risk_reasoning": "one sentence explanation",
  "risk_classification_confidence": "high | medium | low",
  "ai_libraries": ["AI/ML libraries found in dependencies"],
  "source_dirs": ["directories with production code"],
  "test_dirs": ["directories with test code"],
  "generated_files": ["auto-generated files"],
  "config_files": ["configuration files"],
  "doc_files": ["documentation files"],
  "logging_framework": "logging library used, or none",
  "logging_framework_confidence": "high | medium | low",
  "logging_config_file": "path to logging config or empty",
  "monitoring_tools": ["monitoring tools found"],
  "monitoring_tools_confidence": "high | medium | low",
  "monitoring_files": ["monitoring-related files"],
  "test_framework": "test framework used or none",
  "compliance_answers": {{
    "art5": {{
      "is_realtime_processing": null,
      "processing_mode_evidence": "",
      "prohibited_practices": [
        {{
          "practice": "biometric_surveillance",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "social_scoring",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "subliminal_manipulation",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "prohibited_emotion_recognition",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "vulnerability_exploitation",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "criminal_profiling",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }},
        {{
          "practice": "prohibited_real_time_biometrics",
          "detected": null,
          "evidence": "",
          "evidence_paths": [],
          "confidence": "low"
        }}
      ]
    }},
    "art6": {{
      "annex_iii_categories": [],
      "annex_i_product_type": null,
      "is_high_risk": null,
      "reasoning": ""
    }},
    "art9": {{
      "has_risk_docs": null,
      "risk_doc_paths": [],
      "has_testing_infrastructure": null,
      "testing_evidence": [],
      "has_risk_code_patterns": null,
      "risk_code_evidence": [],
      "has_defined_metrics": null,
      "metrics_evidence": [],
      "affects_children": null
    }},
    "art10": {{
      "has_data_governance_doc": null,
      "data_doc_paths": [],
      "has_bias_mitigation": null,
      "bias_evidence": [],
      "has_data_lineage": null
    }},
    "art11": {{
      "has_technical_docs": null,
      "doc_paths": [],
      "documented_aspects": []
    }},
    "art12": {{
      "has_logging": null,
      "logging_description": "",
      "logging_evidence": [],
      "has_retention_config": null,
      "retention_days": null,
      "retention_evidence": ""
    }},
    "art13": {{
      "has_explainability": null,
      "explainability_evidence": [],
      "has_transparency_info": null,
      "transparency_paths": []
    }},
    "art14": {{
      "has_human_oversight": null,
      "oversight_evidence": [],
      "has_override_mechanism": null,
      "override_evidence": []
    }},
    "art15": {{
      "has_accuracy_testing": null,
      "accuracy_evidence": [],
      "has_robustness_testing": null,
      "robustness_evidence": [],
      "has_fallback_behavior": null
    }},
    "art50": {{
      "is_chatbot_or_interactive_ai": null,
      "is_generating_synthetic_content": null,
      "has_ai_disclosure_to_users": null,
      "disclosure_evidence": [],
      "has_content_watermarking": null,
      "is_emotion_recognition_system": null,
      "is_biometric_categorization_system": null,
      "has_emotion_biometric_disclosure": null,
      "emotion_biometric_evidence": [],
      "is_deep_fake_system": null,
      "has_deep_fake_disclosure": null,
      "deep_fake_evidence": []
    }},
    "_scope": {{
      "is_ai_system": null,
      "is_ai_system_reasoning": "explain why this is/isn't an AI system per Art. 3(1)",
      "territorial_scope_applies": null,
      "territorial_scope_reasoning": "is the provider/deployer in EU, or is output used in EU?",
      "is_open_source": null,
      "open_source_license": "license name if open source, e.g. MIT, Apache-2.0",
      "user_role": null,
      "user_role_reasoning": "are you scanning as the provider (developer) or deployer (user) of this system?",
      "is_military_defense": false,
      "is_research_only": false,
      "is_biometric_system": null,
      "is_financial_institution": null
    }},
    "_scan_metadata": {{
      "files_read": ["list every file path you actually read, e.g. src/app.py"],
      "total_project_files": null,
      "scan_notes": "any limitations, e.g. 'skipped 3 binary files', 'config dir not readable'"
    }}
  }}
}}"""


# generate_context_via_api() removed — ComplianceLint is MCP-only.
# In MCP mode, Claude reads the project directly using its own file tools.
# There is no API-based CLI mode. See CLAUDE.md for the architectural decision.
