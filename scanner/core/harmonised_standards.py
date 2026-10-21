"""Harmonised standards and the other instruments each article waits for — one source for the user-facing texts.

Texts: legal review of 2026-10-21 (items T2–T8); reviewer remarks ("not verified in this review") left out,
statements kept only where the source was read.

Cited standards: Commission Implementing Decision (EU) 2026/2274 of 12 October 2026, OJ L 2026/2274, 14.10.2026
(CELEX 32026D2274) — one standard, EN 18286:2026, in force on publication (Art. 2, recital 6). Recital 3: point 9 of
Annex I to C(2025) 3871, "quality management systems for providers of AI systems, including post-market monitoring
processes". The Commission notice of 19 October 2026: "providers implementing this standard will benefit from a
presumption of conformity with the Article 17 requirements covered by the standard". Article 40(1) names Chapter III,
Section 2 (Art. 17 is in Section 3); Regulation (EU) 2026/1744 added the Sections 2 and 3 subparagraph to Article
40(2). The clause-by-clause coverage is in the standard's Annex ZA (not read), so `articles` lists Art. 17 only and
no presumption is stated for Art. 72.
"""

CITED_STANDARDS: tuple[dict, ...] = (
    {
        "reference": "EN 18286:2026",
        "title": "Artificial intelligence — Quality management system for EU AI Act regulatory purposes",
        "articles": (17,),
        "implementing_decision": "Commission Implementing Decision (EU) 2026/2274",
        "celex": "32026D2274",
        "oj_citation": "OJ L 2026/2274, 14.10.2026",
        "published_on": "14 October 2026",
        "presumption_from": "2026-10-14",
        "eli": "http://data.europa.eu/eli/dec_impl/2026/2274/oj",
    },
)

# review T2 / T7 / T8 — the sentences on EN 18286:2026
EN18286_PUBLISHED = (
    "The reference of EN 18286:2026, Artificial intelligence — Quality management system for EU AI Act regulatory "
    "purposes, was published in the Official Journal of the European Union on 14 October 2026 by Commission "
    "Implementing Decision (EU) 2026/2274."
)
EN18286_PRESUMPTION = (
    "The European Commission states that providers implementing EN 18286:2026 benefit from a presumption of "
    "conformity with the Article 17 requirements covered by the standard."
)
EN18286_COVERAGE = (
    "The exact coverage is determined by the standard, in particular Annex ZA, which ComplianceLint has not reviewed."
)

INTERIM_CHECKLIST_PREFIX = (
    "This is an interim checklist developed by ComplianceLint. It is not a harmonised standard and does not itself "
    "give a presumption of conformity."
)

# review T6 — action-plan disclaimer
ACTION_PLAN_DISCLAIMER = (
    "This action plan is based on the ComplianceLint compliance checklist and good practice; it is not a harmonised "
    "standard and does not itself give a presumption of conformity. Where the reference of an applicable harmonised "
    "standard has been published in the Official Journal of the European Union, conformity with that standard gives "
    "a presumption of conformity only for the requirements or obligations covered by the standard. Harmonised "
    "standards do not amend the requirements of Regulation (EU) 2024/1689."
)

_REQUEST = "Commission Implementing Decision C(2025) 3871"
_NO_DATE = "No official date for publication of its reference in the Official Journal of the European Union has been announced."


def _in_development(area: str, point: str) -> str:
    return (
        f"A harmonised standard on {area} is being developed by CEN and CENELEC under {_REQUEST}, Annex I, "
        f"point {point}. {_NO_DATE}"
    )


def _not_in_request(article: int, rest: str) -> str:
    return (
        f"No harmonised standard is requested specifically for Article {article} in the Commission's "
        f"standardisation request ({_REQUEST}). {rest}"
    )


def _gpai_standard(article: int, sections: str, rest: str) -> str:
    return (
        f"Article 40(2) provides for standardisation requests covering, as applicable, the obligations in Chapter V, "
        f"{sections}; no harmonised standard for Article {article} has been published. {rest}"
    )


_GPAI_CODE = (
    "The General-Purpose AI Code of Practice was published on 10 July 2025 and assessed as an adequate voluntary "
    "tool by the Commission and the Board on 1 August 2025."
)
_ART6_DRAFT = "The Commission published draft guidelines on the classification of high-risk AI systems on 19 May 2026."

# review T3 / T4 / T5 — "waiting_for" per article (Articles 5, 48, 49 and 71 keep their module texts)
STANDARD_STATUS: dict[int, str] = {
    4: (
        "No harmonised standard is requested for Article 4. The Regulation instead requires the Commission to "
        "publish practical examples of how to comply on the single information platform (Article 4(2)) and the "
        "Board to adopt recommendations setting out common objectives (Article 4(3)). The Commission has published "
        "an AI-literacy Q&A and a living repository of AI-literacy practices."
    ),
    6: (
        "No harmonised standard is requested for Article 6 classification. Article 6(5) requires Commission "
        f"guidelines with practical examples. {_ART6_DRAFT}"
    ),
    8: (
        f"No separate harmonised standard is requested specifically for Article 8 in {_REQUEST}. Article 8 is the "
        "overarching compliance requirement for high-risk AI systems; the standardisation request develops "
        "technical specifications for the substantive requirements in Articles 9 to 15."
    ),
    9: _in_development("risk management systems for AI systems", "1"),
    10: _in_development("governance and quality of datasets used to build AI systems", "2"),
    11: (
        "No separate harmonised standard or European standardisation deliverable is requested specifically for "
        f"Article 11 technical documentation. {_REQUEST} requires the Article 11 requirements to be fully covered in "
        "the other requested standards and deliverables, particularly the quality-management-system work."
    ),
    12: _in_development("record keeping through logging capabilities by AI systems", "3"),
    13: _in_development("transparency and information provisions for users of AI systems", "4"),
    14: _in_development("human oversight of AI systems", "5"),
    15: (
        "Harmonised standards and, where necessary, European standardisation deliverables on accuracy, robustness "
        f"and cybersecurity specifications for AI systems are being developed under {_REQUEST}, Annex I, points 6 "
        "to 8. No official date for publication of their references in the Official Journal of the European Union "
        "has been announced."
    ),
    16: (
        "Harmonised standards and European standardisation deliverables supporting the Chapter III, Section 2 "
        f"requirements are being developed by CEN and CENELEC under {_REQUEST}. No official date has been announced "
        "for any further publication of references in the Official Journal of the European Union. For the quality "
        "management system required by Article 16(c) through Article 17, the reference of EN 18286:2026 was "
        "published in the Official Journal of the European Union on 14 October 2026 by Commission Implementing "
        f"Decision (EU) 2026/2274. {EN18286_PRESUMPTION}"
    ),
    17: (
        f"A harmonised standard supporting Article 17 is now cited. {EN18286_PUBLISHED} {EN18286_PRESUMPTION} "
        f"{EN18286_COVERAGE}"
    ),
    18: _not_in_request(
        18, "Article 18 applies directly; the Regulation provides no guideline, code of practice, template or "
        "implementing act specific to Article 18."),
    19: _not_in_request(
        19, "Article 19 applies directly; the Regulation provides no further instrument specific to Article 19."),
    20: _not_in_request(20, "The corrective-action and information obligations in Article 20 apply directly."),
    21: _not_in_request(21, "The cooperation obligation in Article 21 applies directly."),
    22: _not_in_request(22, "The authorised-representative obligations in Article 22 apply directly."),
    23: _not_in_request(23, "The importer obligations in Article 23 apply directly."),
    24: _not_in_request(24, "The distributor obligations in Article 24 apply directly."),
    25: _not_in_request(
        25, "Article 96(1)(a) requires Commission guidelines on the practical application of Article 25."),
    26: _not_in_request(
        26, "Article 96(1)(a) requires Commission guidelines on the practical application of Article 26."),
    27: _not_in_request(
        27, "Article 27(5) requires the AI Office to develop a questionnaire template, including through an "
        "automated tool, for the fundamental rights impact assessment. The Commission states that guidance with a "
        "template is being prepared."),
    41: (
        "Article 41 does not require a harmonised standard of its own. It is the fallback mechanism allowing the "
        "Commission, under specified conditions, to adopt implementing acts establishing common specifications when "
        "requested harmonised standards are unavailable or inadequate."
    ),
    43: (
        "A harmonised standard or European standardisation deliverable on conformity assessment for AI systems is "
        f"being developed under {_REQUEST}, Annex I, point 10. No official date for publication of a "
        "harmonised-standard reference, if applicable, has been announced."
    ),
    47: (
        "No harmonised standard is requested for Article 47. Article 47(5) empowers the Commission to adopt "
        "delegated acts updating the content of the EU declaration of conformity in Annex V in light of technical "
        "progress."
    ),
    50: (
        "No harmonised standard is requested for Article 50. The Commission adopted Guidelines on the "
        "implementation of the transparency obligations for certain AI systems under Article 50 on 20 July 2026. "
        "The Code of Practice on Transparency of AI-generated Content was published on 10 June 2026; the Commission "
        "and the Board have confirmed that it is an adequate voluntary tool for the marking and labelling "
        "obligations it covers."
    ),
    51: (
        "No harmonised standard is requested for Article 51; Article 51 is in Chapter V, Section 1, outside the "
        "Chapter V Sections 2 and 3 standardisation route in Article 40. Article 51(3) empowers the Commission to "
        "adopt delegated acts to amend the thresholds and supplement benchmarks and indicators."
    ),
    52: (
        "No harmonised standard is requested for Article 52; Article 52 is in Chapter V, Section 1. Article 52(4) "
        "empowers the Commission to adopt delegated acts amending the criteria in Annex XIII."
    ),
    53: _gpai_standard(
        53, "Sections 2 and 3",
        "Until a harmonised standard is published, Article 53(4) permits providers to rely on codes of practice "
        f"within the meaning of Article 56. {_GPAI_CODE} The Commission has also published guidelines on the "
        "obligations of providers of general-purpose AI models and the template for the summary of training content."),
    54: _gpai_standard(
        54, "Section 2",
        "Article 54 applies directly. The Article 56 code-of-practice mechanism is expressly aimed at the "
        "obligations in Articles 53 and 55, not Article 54."),
    55: _gpai_standard(
        55, "Sections 2 and 3",
        "Until a harmonised standard is published, Article 55(2) permits providers of general-purpose AI models with "
        f"systemic risk to rely on codes of practice within the meaning of Article 56. {_GPAI_CODE}"),
    60: (
        "No harmonised standard is requested for Article 60. Article 60(1) requires Commission implementing acts "
        "specifying the detailed elements of the real-world testing plan."
    ),
    61: (
        "No harmonised standard is requested for Article 61. The informed-consent requirements are set directly by "
        "Article 61; no separate Commission instrument specific to Article 61 is provided. The Article 60 "
        "implementing act concerns the real-world testing plan, not the Article 61 consent obligation itself."
    ),
    72: (
        "No standalone harmonised standard is requested specifically for Article 72. Post-market monitoring "
        f"processes form part of the quality-management-system work item ({_REQUEST}, Annex I, point 9), which "
        "resulted in EN 18286:2026; they are therefore relevant to EN 18286:2026 through Article 17(1)(h), but this "
        "does not create an independent presumption of conformity with Article 72. Article 72(3) requires Commission "
        "guidance, including a template, on the post-market monitoring plan by 2 September 2027."
    ),
    73: (
        "No harmonised standard is requested specifically for Article 73. Article 73(7) requires dedicated "
        "Commission guidance on serious-incident reporting; the Commission published draft guidance and a reporting "
        "template on 26 September 2025."
    ),
    80: (
        "No harmonised standard is requested for Article 80. Article 80(1) requires market surveillance authorities "
        "to evaluate disputed non-high-risk classifications on the basis of the conditions in Article 6(3) and the "
        f"Commission guidelines. {_ART6_DRAFT}"
    ),
    82: (
        "No harmonised standard is requested for Article 82. The procedure for compliant AI systems that "
        "nevertheless present a risk is set directly by Article 82; no secondary instrument specific to Article 82 "
        "is provided."
    ),
    86: (
        "No harmonised standard is requested for Article 86. The right to obtain a clear and meaningful explanation "
        "in the circumstances defined by Article 86 applies directly; the Article does not provide for a standard, "
        "code, template or implementing act specific to Article 86."
    ),
    91: (
        "No harmonised standard is requested for Article 91. The Commission's power to request documentation and "
        "information from providers of general-purpose AI models is set directly by Article 91; no secondary "
        "instrument specific to Article 91 is provided."
    ),
    92: (
        "No harmonised standard is requested for Article 92. Article 92(6) requires Commission implementing acts "
        "setting out the detailed arrangements and conditions for the evaluations of general-purpose AI models, "
        "including the involvement and selection of independent experts."
    ),
    111: (
        "No harmonised standard is requested for Article 111. Article 111 is a transitional provision and applies "
        "directly; the Regulation does not provide a harmonised standard or guidance instrument specific to "
        "Article 111."
    ),
}


def standard_status(article_number: int) -> str:
    """The article's "waiting_for" text (KeyError for an article without one — a module must not invent it)."""
    return STANDARD_STATUS[article_number]


def interim_checklist_disclaimer(article_number: int) -> str:
    """Review T7 — the interim-checklist disclaimer for an article."""
    if article_number == 17:
        return f"{INTERIM_CHECKLIST_PREFIX} {EN18286_PUBLISHED} {EN18286_PRESUMPTION} {EN18286_COVERAGE}"
    return f"{INTERIM_CHECKLIST_PREFIX} {standard_status(article_number)}"


def cited_for_article(article_number: int) -> list[dict]:
    """The cited harmonised standards announced for an article (JSON-ready: `articles` as a list)."""
    return [
        {**std, "articles": list(std["articles"])}
        for std in CITED_STANDARDS
        if article_number in std["articles"]
    ]


def update_check_status(std: dict) -> str:
    """Review T8(a) — the status line of `cl_check_updates`."""
    return (
        f"Harmonised standard: its reference was published in the Official Journal of the European Union on "
        f"{std['published_on']} by {std['implementing_decision']}. {EN18286_PRESUMPTION} The exact scope is "
        "determined by the standard, in particular Annex ZA."
    )
