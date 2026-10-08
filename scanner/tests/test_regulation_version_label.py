"""Regulation label in scan output names the amended text (founder 2026-10-08).

The single-article scan already said "Regulation (EU) 2024/1689, as amended by Regulation (EU) 2026/1744"; the
full-scan report and the cl_scan tool description still named only the 2024 regulation, and the action-plan
disclaimer pointed to "the official Regulation (EU) 2024/1689 text" as the binding text. Recital texts keep the 2024
citation: the preamble exists only in the original Official Journal text.
"""
from pathlib import Path

SERVER = (Path(__file__).resolve().parents[1] / "server.py").read_text(encoding="utf-8")
LABEL = "EU AI Act (Regulation (EU) 2024/1689, as amended by Regulation (EU) 2026/1744)"


def test_every_report_regulation_field_uses_the_amended_label():
    lines = [ln.strip() for ln in SERVER.splitlines() if ln.strip().startswith('"regulation": "EU AI Act')]
    assert len(lines) >= 2
    assert all(ln == f'"regulation": "{LABEL}",' for ln in lines), lines


def test_tool_description_names_the_amended_text():
    assert '"eu-ai-act" (default) — EU AI Act (Regulation (EU) 2024/1689)\n' not in SERVER
    assert f'"eu-ai-act" (default) — {LABEL}' in SERVER


def test_binding_text_pointer_is_the_consolidated_text():
    assert "official Regulation (EU) 2024/1689 text for " not in SERVER
