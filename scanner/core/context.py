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
    "art8":  ["section_2_evidence"],
    "art5":  ["prohibited_practices"],
    "art6":  ["annex_iii_categories"],
    "art9":  ["risk_doc_paths", "testing_evidence", "risk_code_evidence", "metrics_evidence"],
    "art10": ["data_doc_paths", "bias_evidence"],
    "art11": ["doc_paths", "documented_aspects"],
    "art12": ["logging_evidence"],
    "art13": ["explainability_evidence", "transparency_paths"],
    "art14": ["oversight_evidence", "override_evidence"],
    "art15": ["accuracy_evidence", "robustness_evidence"],
    "art17": ["qms_evidence"],
    "art18": [],
    "art19": [],
    "art20": [],
    "art21": [],
    "art43": [],
    "art47": [],
    "art50": ["disclosure_evidence", "emotion_biometric_evidence", "deep_fake_evidence"],
    "art4":  ["literacy_evidence"],
    "art16": [],
    "art22": [],
    "art23": [],
    "art24": [],
    "art25": [],
    "art26": [],
    "art27": [],
    "art41": [],
    "art49": [],
    "art51": [],
    "art52": [],
    "art53": ["documentation_evidence", "downstream_doc_evidence"],
    "art54": ["representative_evidence"],
    "art55": ["evaluation_evidence"],
    "art60": [],
    "art61": [],
    "art71": [],
    "art72": [],
    "art73": [],
    "art80": [],
    "art82": [],
    "art86": [],
    "art91": [],
    "art92": [],
    "art111": [],
}

# Fields that must be bool or None (never strings like "true")
_BOOL_FIELDS: dict = {
    "art8":  ["has_section_2_compliance", "is_annex_i_product", "has_annex_i_compliance"],
    "art5":  ["is_realtime_processing"],
    "art6":  ["is_high_risk"],
    "art9":  ["has_risk_docs", "has_testing_infrastructure", "has_risk_code_patterns", "has_defined_metrics", "affects_children"],
    "art10": ["has_data_governance_doc", "has_bias_mitigation", "has_data_lineage", "processes_special_category_data"],
    "art11": ["has_technical_docs", "is_annex_i_product"],
    "art12": ["has_logging", "has_retention_config"],
    "art13": ["has_explainability", "has_transparency_info"],
    "art14": ["has_human_oversight", "has_override_mechanism"],
    "art15": ["has_accuracy_testing", "has_robustness_testing", "has_fallback_behavior", "continues_learning_after_deployment"],
    "art17": ["has_qms_documentation", "has_compliance_strategy", "has_design_procedures",
              "has_qa_procedures", "has_testing_procedures", "has_technical_specifications",
              "has_data_management", "has_risk_management_in_qms", "has_post_market_monitoring",
              "has_record_keeping", "has_accountability_framework"],
    "art18": ["has_documentation_retention_policy"],
    "art19": ["has_log_retention", "has_retention_config"],
    "art43": ["has_internal_control_assessment", "has_change_management_procedures"],
    "art47": ["has_doc_declaration", "has_annex_v_content"],
    "art50": ["is_chatbot_or_interactive_ai", "is_generating_synthetic_content",
              "has_ai_disclosure_to_users", "has_content_watermarking",
              "is_emotion_recognition_system", "is_biometric_categorization_system",
              "has_emotion_biometric_disclosure", "is_deep_fake_system",
              "has_deep_fake_disclosure"],
    "art20": ["has_corrective_action_procedure", "has_supply_chain_notification",
              "has_risk_investigation_procedure"],
    "art72": ["has_pmm_system", "has_active_data_collection", "has_pmm_plan"],
    "art73": ["has_incident_reporting_procedure", "has_reporting_timelines",
              "has_expedited_reporting_procedure", "has_investigation_procedure"],
    "art86": ["has_explanation_mechanism"],
    "art21": ["has_conformity_documentation", "has_log_export_capability"],
    "art23": ["is_importer", "has_pre_market_verification", "has_conformity_review",
              "has_importer_identification", "has_documentation_retention",
              "has_authority_documentation"],
    "art24": ["is_distributor", "has_pre_market_verification", "has_conformity_review",
              "has_authority_documentation"],
    "art91": ["has_information_supply_readiness"],
    "art92": ["has_evaluation_cooperation_readiness"],
    "art111": ["has_transition_plan", "has_significant_change_tracking", "has_gpai_compliance_timeline"],
    "art4":  ["has_ai_literacy_measures"],
    "art16": ["has_section_2_compliance", "has_provider_identification", "has_qms"],
    "art22": ["is_eu_established_provider", "has_authorised_representative", "has_representative_enablement"],
    "art25": ["has_rebranding_or_modification", "has_provider_cooperation_documentation", "is_safety_component_annex_i"],
    "art26": ["has_deployment_documentation", "has_human_oversight_assignment", "has_operational_monitoring"],
    "art27": ["has_fria_documentation", "has_fria_versioning"],
    "art41": ["follows_common_specifications", "has_alternative_justification"],
    "art49": ["has_eu_database_registration"],
    "art51": ["is_gpai_model", "has_high_impact_capabilities", "training_compute_exceeds_threshold"],
    "art52": ["has_commission_notification"],
    "art53": ["has_technical_documentation", "has_downstream_documentation"],
    "art54": ["is_third_country_provider", "has_authorised_representative", "has_written_mandate"],
    "art55": ["has_systemic_risk", "has_model_evaluation", "has_adversarial_testing"],
    "art60": ["has_testing_plan", "has_incident_reporting_for_testing", "has_authority_notification_procedure"],
    "art61": ["has_informed_consent_procedure", "has_consent_documentation"],
    "art71": ["has_provider_database_entry"],
    "art80": ["has_compliance_remediation_plan", "has_corrective_action_for_all_systems", "has_classification_rationale"],
    "art82": ["has_corrective_action_procedure"],
    "_scope": ["is_ai_system", "territorial_scope_applies", "is_open_source",
               "is_military_defense", "is_research_only",
               "is_biometric_system", "is_financial_institution", "is_distributor",
               "is_importer", "is_gpai_provider",
               # 2026-04-29 Phase 3 §E — schema sync. AR was added to SaaS UI
               # + DB + scan-settings API on 2026-04-26 (commits 541dfcf,
               # 28d3fcd) but the scanner _scope schema was never updated.
               # Free MCP without SaaS connection had AI-supplied
               # is_authorised_representative silently dropped because the
               # schema didn't recognize the field.
               "is_authorised_representative"],
    # NOTE on sme_status: this is a STRING enum (microenterprise/small/
    # medium/large per Recommendation 2003/361/EC), NOT a bool. It MUST
    # NOT live in _BOOL_FIELDS — the coerce step would try to map the
    # string to bool/None and silently destroy it. Like risk_classification,
    # sme_status is read directly from _scope when needed and is populated
    # by _apply_saas_settings_to_scope on paid tiers (Phase 2 §B). No
    # standalone validation is needed at the AI-template stage; the SaaS
    # response is the authority for paid users, and scanner falls back to
    # absent/None for free + offline.
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
    # risk_classification holds the EU AI Act legal category. The 4 canonical
    # values map 1:1 to dashboard RISK_OPTIONS and to the law itself:
    #   - prohibited (Art. 5)
    #   - high-risk (Art. 6 + Annex III)
    #   - limited-risk (Art. 50 transparency obligations)
    #   - minimal-risk (no specific obligations)
    # AI uncertainty about WHICH category applies goes in the separate
    # `risk_classification_confidence` field, NOT mixed into the value (i.e.
    # "likely high-risk" is no longer accepted — use risk_classification="high-risk"
    # plus risk_classification_confidence="medium" instead).
    risk_classification: str = ""        # one of: prohibited | high-risk | limited-risk | minimal-risk | "" (empty when AI cannot determine)
    risk_reasoning: str = ""             # Why the AI thinks so (free text)
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


def _build_answers_template() -> dict:
    """Build a complete empty compliance_answers template from _BOOL_FIELDS and _LIST_FIELDS.

    Every article key with all its fields pre-set to null (bools) or [] (lists).
    The AI fills in values; unfilled fields remain null → UNABLE_TO_DETERMINE.

    This is returned by cl_analyze_project() so the AI has an exact template
    to fill rather than inventing its own keys.
    """
    template = {}
    all_articles = sorted(set(_BOOL_FIELDS.keys()) | set(_LIST_FIELDS.keys()))
    for art_key in all_articles:
        if art_key.startswith("_"):
            continue  # _scope is handled separately
        fields = {}
        for field_name in _BOOL_FIELDS.get(art_key, []):
            fields[field_name] = None
        for field_name in _LIST_FIELDS.get(art_key, []):
            fields[field_name] = []
        template[art_key] = fields

    # Add _scope separately
    template["_scope"] = {}
    for field_name in _BOOL_FIELDS.get("_scope", []):
        template["_scope"][field_name] = None

    return template


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

    # ── 8. Empty compliance_answers template ──
    # Provide a pre-built template with ALL article keys and their fields set to null/[].
    # This forces the AI to fill every field — not just the ones it thinks are relevant.
    answers_template = _build_answers_template()

    # ── 9. Configuration status check ──
    # Detect missing setup so AI can guide user proactively.
    from core.config import ProjectConfig
    config = ProjectConfig.load(project_path)
    setup_warnings = []
    if not config.saas_api_key:
        setup_warnings.append(
            "No dashboard connection. Run cl_connect() to link your project "
            "to the ComplianceLint dashboard for tracking and reporting."
        )
    if not config.attester_name or not config.attester_email:
        setup_warnings.append(
            "No attester identity configured. This is needed for submitting "
            "evidence (cl_update_finding). It will be auto-set when you run "
            "cl_connect(), or you can add attester_name and attester_email "
            "to .compliancelintrc manually."
        )

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
        "compliance_answers_template": answers_template,
        "setup_warnings": setup_warnings if setup_warnings else None,
    }


# ── compliance_answers Schema Reference ──
#
# The schema is NOT hardcoded here. It is dynamically generated from
# _BOOL_FIELDS and _LIST_FIELDS by _build_answers_template().
#
# cl_analyze_project() returns the template in its response as
# "compliance_answers_template". The AI copies this template and fills
# in values. The validation gate enforces correctness.
#
# Single source of truth: _BOOL_FIELDS + _LIST_FIELDS (above).
# Everything else derives from them automatically.
#
# DEPRECATED: COMPLIANCE_ANSWERS_SCHEMA below is kept for backward
# compatibility but is NOT the source of truth. Do not update it —
# update _BOOL_FIELDS/_LIST_FIELDS instead.

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
  "risk_classification": "prohibited | high-risk | limited-risk | minimal-risk | \"\" (empty if you cannot determine yet)",
  "risk_reasoning": "one sentence explanation. Use this to express uncertainty (e.g. 'leaning high-risk because Annex III §1 may apply, but need confirmation of the deployment context'). Do NOT put 'likely' / 'unclear' inside risk_classification itself — use confidence instead.",
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
      "user_role_reasoning": "are you scanning as the provider (3(3) — developer/manufacturer), deployer (3(4) — operational user), authorised representative (3(5) — EU rep for non-EU provider), importer (3(6)), or distributor (3(7)) per EU AI Act Art. 3?",
      "is_military_defense": false,
      "is_research_only": false,
      "is_biometric_system": null,
      "is_financial_institution": null,
      "is_distributor": null,
      "is_importer": null,
      "is_gpai_provider": null,
      "risk_classification": "prohibited | high-risk | limited-risk | minimal-risk | \"\" (empty if you cannot determine)",
      "risk_classification_confidence": "high | medium | low",
      "risk_reasoning": "one sentence explanation. Use this for uncertainty (e.g. 'leaning high-risk pending confirmation'). Do NOT put 'likely' / 'unclear' inside risk_classification itself."
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
