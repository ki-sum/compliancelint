"""ComplianceLint project configuration (.compliancelintrc support)."""
import json
import os
from dataclasses import dataclass, field


@dataclass
class ProjectConfig:
    """User-defined project configuration for ComplianceLint.

    Create .compliancelintrc in your project root to override AI classifications.
    Use overrides when AI confidence is low.

    Example .compliancelintrc:
    {
        "risk_classification_override": "minimal-risk",
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
    # Use these when AI confidence is "low" or you disagree with the AI.
    # risk_classification_override accepts the 4 canonical EU AI Act categories
    # (matching the dashboard RISK_OPTIONS):
    #   prohibited | high-risk | limited-risk | minimal-risk
    # Backward-compat: legacy strings ("not high-risk", "likely high-risk", "low-risk",
    # "limited risk", "minimal risk") are still accepted by `_NOT_HIGH_RISK_VALUES` in
    # protocol.py for the article-skip path, but NEW configs should use canonical
    # values to avoid amber-mismatch banners in the SaaS dashboard.
    risk_classification_override: str = ""        # canonical: "minimal-risk" | "limited-risk" | "high-risk" | "prohibited"
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

        Uses asyncio subprocess (post 2026-05-06 hypothesis-C verification:
        asyncio.create_subprocess_exec on Windows uses ProactorEventLoop's
        IOCP machinery, NOT subject to the documented MCP+subprocess.run
        race per memory bug_mcp_tool_hang.md).

        Only runs git if repo_name or project_id are not already set.
        """
        if self.repo_name and self.project_id:
            return  # Already have both, skip git

        import asyncio as _asyncio
        import hashlib
        import subprocess as _sp
        import sys as _sys

        async def _run(*args: str) -> tuple[int, str]:
            creationflags = 0
            if hasattr(_sp, "CREATE_NO_WINDOW"):
                creationflags = _sp.CREATE_NO_WINDOW
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "git", *args,
                    cwd=project_path,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                    creationflags=creationflags,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
            except (FileNotFoundError, OSError):
                return -1, ""
            try:
                stdout, _stderr = await _asyncio.wait_for(
                    proc.communicate(), timeout=5.0,
                )
            except _asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.communicate()
                except Exception:
                    pass
                return -1, ""
            return (
                proc.returncode if proc.returncode is not None else -1,
                stdout.decode("utf-8", errors="replace"),
            )

        async def _gather():
            url_rc, url_out = await _run("remote", "get-url", "origin")
            url = url_out.strip() if url_rc == 0 else ""
            root_hash = ""
            if url:
                root_rc, root_out = await _run("rev-list", "--max-parents=0", "HEAD")
                if root_rc == 0:
                    lines = [ln for ln in root_out.splitlines() if ln.strip()]
                    root_hash = lines[0] if lines else ""
            return url, root_hash

        try:
            if _sys.platform == "win32" and hasattr(
                _asyncio, "WindowsProactorEventLoopPolicy",
            ):
                try:
                    _asyncio.set_event_loop_policy(
                        _asyncio.WindowsProactorEventLoopPolicy()
                    )
                except Exception:
                    pass
            url, root_hash = _asyncio.run(_gather())
        except Exception:
            url, root_hash = "", ""

        if url:
            if not self.repo_name:
                if ":" in url and "@" in url:
                    self.repo_name = url.split(":")[-1].replace(".git", "")
                elif "/" in url:
                    parts = url.rstrip("/").replace(".git", "").split("/")
                    if len(parts) >= 2:
                        self.repo_name = f"{parts[-2]}/{parts[-1]}"

            if not self.project_id:
                material = f"{url}:{root_hash}"
                self.project_id = f"git-{hashlib.sha256(material.encode()).hexdigest()[:16]}"

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
