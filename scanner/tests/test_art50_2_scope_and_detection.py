"""Article 50(2): which outputs count, and what a "yes" to marking must say about detection (legal review o3 AA,
2026-10-26; conditions of review Z).

`is_generating_synthetic_content` had no description, so an assistant could count generated source code as synthetic
text and get the CRITICAL marking action. It now follows the Commission's non-binding Guidelines C(2026) 5054,
paragraph 68: source code, short labels, machine-to-machine and non-final closed-loop outputs do not count, while
substantive natural-language answers, documents and images do; the statutory exceptions apply.

`has_content_watermarking` keeps its meaning ("a marking mechanism was identified", evidence for review): requiring a
detector for "yes" would turn marks without a detector into "no" and the wrong "Mark ... outputs" action. Instead the
evidence names, per mechanism, how an exposed person can detect the mark, or says that no means was found; a flag,
field, manifest or log alone proves nothing. `marking_evidence` records gaps and negative findings too.
"""
import os
import sys

SCANNER_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCANNER_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from test_art50_evidence_fields import _analyze  # noqa: E402

SYNTHETIC_CONTENT_DESCRIPTION = (
    'true if the AI system generates or substantially manipulates at least one in-scope synthetic audio, image, '
    'video or text output intended to be perceived, interpreted, verified or acted upon by natural persons for the '
    "purposes of Article 50(2). Apply the Commission's non-binding Guidelines C(2026) 5054, paragraph 68, as "
    'interpretative guidance. Do not count: short sequences such as single words, brief image captions, alt-text, '
    'UI labels or icon-scale graphics; source code in programming, scripting, markup, query or configuration '
    'languages intended to be interpreted, compiled or executed by software, including comments and contextual '
    'information integral to that code, and technical artefacts such as SDKs, SQL, infrastructure-as-code, YAML or '
    'JSON configuration, schemas, scripts, machine-readable specifications, APIs and software libraries; '
    'exclusively machine-to-machine outputs processed without human exposure; or non-final outputs used only in '
    'closed-loop production workflows. Do not automatically exclude substantive human-readable content merely '
    'because it is carried in JSON or markup, or because it relates to programming. Apply the Article 50(2) '
    "exceptions for assistive standard editing, no substantial alteration of the deployer's input or its semantics,"
    ' and legally authorised criminal-law-enforcement uses where applicable. A coding assistant whose only output '
    'is excluded source code answers false; one that also produces substantive natural-language answers, standalone'
    ' documentation, images or other in-scope human-facing content answers true. For true, name the in-scope output'
    ' types and paths in marking_evidence. Answer false if the evidence establishes that there are no in-scope '
    'outputs; null if the available project evidence is insufficient to determine this. This field assesses output '
    'scope, not the identity of the legally responsible provider or the applicable compliance date.'
)

MARKING_DESCRIPTION = (
    'true if at least one in-scope synthetic audio, image, video or text output type or path has an identifiable '
    'implementation intended to apply or associate a machine-readable mark indicating artificial generation or '
    'manipulation, such as embedded metadata, watermarking, a provenance signature or another technical marking '
    'mechanism. Detection does not have to be independently verified for this evidence flag to be true: true '
    'indicates an identified marking mechanism requiring human review, not compliance with Article 50(2). false if '
    'no such marking mechanism is identified for any in-scope synthetic output; null if the available project '
    'evidence is insufficient to determine whether a mechanism exists. Do not treat a standalone watermark '
    'configuration flag, declared metadata field or manifest format, or server log as proof that an output is '
    'actually marked. In marking_evidence, identify each mechanism and its code or configuration location where '
    'available; state which delivered output types and paths it covers, and how a person potentially exposed to the'
    ' output can access a means of detection and obtain human-readable results (for example, an appropriate '
    'publicly available C2PA verifier, an accessible model-provider watermark detector, or an available provider or'
    ' third-party detection service). If no detection means or access path was identified, say so explicitly. Also '
    'identify in-scope output types and paths for which marking or detectability is missing or cannot be verified. '
    'A mark, field, manifest, log or configuration flag alone does not establish detectability or Article 50(2) '
    'compliance.'
)

MARKING_EVIDENCE_DESCRIPTION = (
    'List free-text items describing the marking and detection evidence, gaps and uncertainties for in-scope '
    'synthetic audio, image, video or text outputs under Article 50(2). For each relevant output type or path, '
    'identify the machine-readable marking mechanism, its code or configuration location where available, and the '
    'means by which a person potentially exposed to the delivered output can detect artificial generation or '
    'manipulation and obtain human-readable results. If no means of detection or access path was identified, state '
    'this explicitly rather than assuming that metadata, a C2PA manifest, a server log or a configuration flag '
    'proves detectability. Identify output paths that are unmarked or for which marking or detection cannot be '
    'verified, including where another path is marked. If an in-scope output is identified but no marking mechanism'
    ' is found, record that negative finding; use an empty list only when there is no relevant evidence or '
    'identifiable in-scope output path to report.'
)


def _descs(tmp_path):
    return _analyze(tmp_path)["compliance_answers_field_descriptions"]["art50"]


def test_the_scope_question_is_described(tmp_path):
    assert _descs(tmp_path)["is_generating_synthetic_content"] == SYNTHETIC_CONTENT_DESCRIPTION


def test_source_code_only_is_out_of_scope_but_chat_answers_are_not(tmp_path):
    d = _descs(tmp_path)["is_generating_synthetic_content"]
    assert "A coding assistant whose only output is excluded source code answers false" in d
    assert "substantive natural-language answers, standalone documentation, images" in d
    assert "non-binding Guidelines C(2026) 5054, paragraph 68" in d


def test_the_marking_answer_asks_for_the_means_of_detection(tmp_path):
    d = _descs(tmp_path)["has_content_watermarking"]
    assert d == MARKING_DESCRIPTION
    assert "If no detection means or access path was identified, say so explicitly." in d


def test_the_evidence_list_records_gaps_and_negative_findings(tmp_path):
    d = _descs(tmp_path)["marking_evidence"]
    assert d == MARKING_EVIDENCE_DESCRIPTION
    assert "Empty list if no such evidence is found" not in d
