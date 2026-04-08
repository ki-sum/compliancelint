"""ComplianceLint project configuration (.compliancelintrc support)."""
import json
import os
from dataclasses import dataclass, field


@dataclass
class ProjectConfig:
    """User-defined project configuration for ComplianceLint.

    Create .compliancelintrc in your project root to override AI classifications.
    Use overrides when AI confidence is low or classification is "unclear".

    Example .compliancelintrc:
    {
        "risk_classification_override": "not high-risk",
        "risk_classification_reasoning": "CRUD app, no AI decision-making",
        "primary_language_override": "typescript",
        "logging_framework_override": "winston",
        "monitoring_tools_override": ["prometheus", "grafana"],
        "skip_articles": [5, 6],
        "process_managed_externally": {
            "art9": "Risk assessment in Confluence: https://wiki.example.com/risk"
        }
    }
    """
    skip_articles: list[int] = field(default_factory=list)
    process_managed_externally: dict[str, str] = field(default_factory=dict)
    custom_source_dirs: list[str] = field(default_factory=list)
    custom_test_dirs: list[str] = field(default_factory=list)

    # ── Scan mode ──
    # "ask"        (default) — when evidence is missing, AI pauses and asks the user
    #                          whether the document exists elsewhere. Suitable for
    #                          interactive sessions (Claude Code, Cursor, Windsurf).
    # "automation" — silent scan, no interruptions. Suitable for CI/CD pipelines,
    #                automated reporting, or when evidence is pre-declared in
    #                compliance-evidence.json.
    scan_mode: str = "ask"   # "ask" | "automation"

    # ── AI classification overrides ──
    # Use these when AI confidence is "low" or risk_classification is "unclear"
    risk_classification_override: str = ""        # "likely high-risk" | "not high-risk"
    risk_classification_reasoning: str = ""       # Your reasoning (included in report)
    primary_language_override: str = ""           # e.g. "typescript", "python"
    logging_framework_override: str = ""          # e.g. "winston", "structlog"
    monitoring_tools_override: list[str] = field(default_factory=list)  # e.g. ["prometheus"]

    # ── Attester identity (for cl_update_finding audit trail) ──
    attester_name: str = ""                       # e.g. "John Chen"
    attester_email: str = ""                      # e.g. "john@company.com"
    attester_role: str = ""                       # e.g. "CTO"

    # ── SaaS Dashboard connection ──
    saas_api_key: str = ""                        # API key from cl_connect
    saas_url: str = "https://compliancelint.dev"  # Dashboard URL
    auto_sync: bool = False                       # Auto-sync results after scan
    repo_name: str = ""                           # Override repo name for dashboard
    project_id: str = ""                          # Override project identity (skip git)

    @classmethod
    def load(cls, project_path: str) -> "ProjectConfig":
        """Load .compliancelintrc from project root. Returns empty config if not found."""
        for name in ['.compliancelintrc', '.compliancelintrc.json', 'compliancelint.json']:
            path = os.path.join(project_path, name)
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return cls(
                        skip_articles=data.get('skip_articles', []),
                        process_managed_externally=data.get('process_managed_externally', {}),
                        custom_source_dirs=data.get('custom_source_dirs', []),
                        custom_test_dirs=data.get('custom_test_dirs', []),
                        scan_mode=data.get('scan_mode', 'ask'),
                        risk_classification_override=data.get('risk_classification_override', ''),
                        risk_classification_reasoning=data.get('risk_classification_reasoning', ''),
                        primary_language_override=data.get('primary_language_override', ''),
                        logging_framework_override=data.get('logging_framework_override', ''),
                        monitoring_tools_override=data.get('monitoring_tools_override', []),
                        attester_name=data.get('attester', {}).get('name', '') if isinstance(data.get('attester'), dict) else data.get('attester_name', ''),
                        attester_email=data.get('attester', {}).get('email', '') if isinstance(data.get('attester'), dict) else data.get('attester_email', ''),
                        attester_role=data.get('attester', {}).get('role', '') if isinstance(data.get('attester'), dict) else data.get('attester_role', ''),
                        saas_api_key=data.get('saas_api_key', ''),
                        saas_url=data.get('saas_url', 'https://compliancelint.dev'),
                        auto_sync=data.get('auto_sync', False),
                        repo_name=data.get('repo_name', ''),
                        project_id=data.get('project_id', ''),
                    )
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
        return cls()

    @property
    def is_ask_mode(self) -> bool:
        """Return True if the scanner should pause and ask the user about missing evidence."""
        return self.scan_mode != "automation"

    @property
    def has_config(self) -> bool:
        return bool(self.skip_articles or self.process_managed_externally
                    or self.custom_source_dirs or self.custom_test_dirs
                    or self.risk_classification_override or self.primary_language_override
                    or self.logging_framework_override or self.monitoring_tools_override
                    or self.saas_api_key)

    def get_attester(self, project_path: str = "") -> dict | None:
        """Get attester identity from .compliancelintrc config.

        Returns dict with name/email/role/source, or None if no identity found.

        IMPORTANT: Does NOT call git subprocess. In MCP context, git hangs
        the event loop. Attester must be set in .compliancelintrc by
        `npx compliancelint init` (which runs in normal terminal, not MCP).
        """
        if self.attester_name and self.attester_email:
            return {
                "name": self.attester_name,
                "email": self.attester_email,
                "role": self.attester_role,
                "source": "compliancelintrc",
            }
        # No git fallback — git subprocess hangs in MCP context.
        # npx compliancelint init should pre-populate attester in .compliancelintrc.
        return None

    def derive_git_identity(self, project_path: str) -> None:
        """Derive repo_name + project_id from git. Sets self.repo_name and self.project_id.

        Safe to call in MCP context: uses timeout=2, GIT_TERMINAL_PROMPT=0, CREATE_NO_WINDOW.
        Only runs git if repo_name or project_id are not already set.
        """
        if self.repo_name and self.project_id:
            return  # Already have both, skip git

        import subprocess
        import hashlib
        try:
            git_flags = {"capture_output": True, "text": True, "cwd": project_path, "timeout": 2,
                         "env": {**os.environ, "GIT_TERMINAL_PROMPT": "0"}}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                git_flags["creationflags"] = subprocess.CREATE_NO_WINDOW

            r = subprocess.run(["git", "remote", "get-url", "origin"], **git_flags)
            if r.returncode == 0:
                url = r.stdout.strip()
                # Derive repo_name from remote URL
                if not self.repo_name:
                    if ":" in url and "@" in url:
                        self.repo_name = url.split(":")[-1].replace(".git", "")
                    elif "/" in url:
                        parts = url.rstrip("/").replace(".git", "").split("/")
                        if len(parts) >= 2:
                            self.repo_name = f"{parts[-2]}/{parts[-1]}"

                # Derive project_id: SHA256(remote_url:root_commit)
                if not self.project_id and url:
                    r2 = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], **git_flags)
                    root_hash = r2.stdout.strip().split("\n")[0] if r2.returncode == 0 else ""
                    material = f"{url}:{root_hash}"
                    self.project_id = f"git-{hashlib.sha256(material.encode()).hexdigest()[:16]}"
        except Exception:
            pass

        if not self.repo_name:
            self.repo_name = os.path.basename(os.path.normpath(project_path))

    def save(self, project_path: str) -> str:
        """Save/update .compliancelintrc in project root. Merges with existing data.

        Returns the path to the written config file.
        """
        config_path = os.path.join(project_path, '.compliancelintrc')

        # Load existing data to preserve fields we don't manage
        existing = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = {}

        # Update with current fields (only write non-default values)
        if self.saas_api_key:
            existing['saas_api_key'] = self.saas_api_key
        if self.saas_url and self.saas_url != 'https://compliancelint.dev':
            existing['saas_url'] = self.saas_url
        if self.auto_sync:
            existing['auto_sync'] = self.auto_sync
        if self.repo_name:
            existing['repo_name'] = self.repo_name
        if self.project_id:
            existing['project_id'] = self.project_id
        if self.attester_name or self.attester_email:
            existing['attester_name'] = self.attester_name
            existing['attester_email'] = self.attester_email
            if self.attester_role:
                existing['attester_role'] = self.attester_role

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
            f.write('\n')

        return config_path
