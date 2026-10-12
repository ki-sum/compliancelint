"""Scanner texts that describe the dashboard's Profiling Wizard follow the role-first wizard (2026-10-12).

Since that wizard, "provider" is an answer the user gives, the risk class is concluded from the answers (there is no
picker), and the dashboard's applicability profile excludes the provider's duties when the answers do not establish
provider status. The scanner still told the AI client about "a quick 30-second wizard about your role and risk
class", to "configure your role and risk classification" in Settings, and that provider duties are never excluded.
"""
import os
import re

SCANNER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.dirname(SCANNER_ROOT)


def _read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _flat(text: str) -> str:
    """Source text with string-literal joins and box borders removed, whitespace collapsed."""
    text = text.replace("║", " ")
    text = re.sub(r"""["']\s*\n\s*f?["']""", "", text)
    return re.sub(r"\s+", " ", text)


def test_no_text_states_a_duration_for_the_wizard():
    for rel in ("scanner/server.py", "bin/init.js"):
        assert not re.search(r"\d+-second wizard|quick .{0,12}wizard", _read(rel)), rel


def test_no_text_says_the_user_states_or_configures_a_risk_class():
    server = _flat(_read("scanner/server.py"))
    assert "and risk class." not in server
    assert "configure your role and risk classification" not in server
    assert "review your AI-detected risk classification in Settings" not in server
    assert "your role + risk" not in _read("bin/init.js")


def test_onboarding_hint_describes_the_role_first_wizard():
    server = _flat(_read("scanner/server.py"))
    assert "you state your role(s) (Provider / Deployer / Importer / etc.) and answer questions about scope and use" in server
    assert "the risk class is concluded from your answers" in server
    assert "On a Starter plan or higher" in server


def test_role_configuration_hint_points_to_the_wizard():
    server = _flat(_read("scanner/server.py"))
    assert "run the Profiling Wizard at compliancelint.dev/dashboard -> [repo] -> Settings -> Run Wizard" in server
    assert "only applicable articles scanned (faster, more accurate)" not in server


def test_init_script_describes_the_role_first_wizard():
    init = _read("bin/init.js")
    assert "Connecting is free" in init
    assert "On a Starter plan or higher, the Profiling Wizard" in init
    assert "concludes the risk class" in init


def test_ai_scope_instructions_give_the_display_label_of_every_stored_risk_value():
    import sys
    sys.path.insert(0, SCANNER_ROOT)
    from core.ai_recommended_scope import RISK_DISPLAY_LABELS, _INSTRUCTIONS

    assert set(RISK_DISPLAY_LABELS) == {"prohibited", "high-risk", "limited-risk", "minimal-risk"}
    for value, label in RISK_DISPLAY_LABELS.items():
        assert f"'{value}'" in _INSTRUCTIONS
        assert label in _INSTRUCTIONS
    # "limited-risk" / "minimal-risk" are stored values, not classes of the Regulation.
    assert "EU AI Act categories" not in _INSTRUCTIONS
    assert "not classes of the Regulation" in _INSTRUCTIONS
    for label in (RISK_DISPLAY_LABELS["limited-risk"], RISK_DISPLAY_LABELS["minimal-risk"]):
        assert label.startswith("Not high-risk")
