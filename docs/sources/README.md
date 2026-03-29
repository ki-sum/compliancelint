# Official Regulation Source Documents

This directory stores **locally downloaded copies** of official regulation texts.

## Why local copies?

EUR-Lex and other official legal databases block automated/programmatic access via AWS WAF.
Browser access works fine, but scripts cannot download directly.

Strategy:
- Human downloads official PDF/HTML from the official source
- File saved here with standardized naming
- SHA-256 hash computed and recorded in the manifest below
- ComplianceLint reads and verifies against these local copies

## Download Instructions

### EU AI Act (Regulation (EU) 2024/1689)

1. Open in browser: https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689
2. Save as: `eu-ai-act-2024-1689-en.pdf`
3. Place in this directory: `docs/sources/eu-ai-act-2024-1689-en.pdf`
4. Compute hash: `sha256sum docs/sources/eu-ai-act-2024-1689-en.pdf` (Linux/Mac) or `Get-FileHash docs/sources/eu-ai-act-2024-1689-en.pdf -Algorithm SHA256` (Windows PowerShell)

## Downloaded Files

| File | Regulation | Version | Downloaded | SHA-256 | Verified |
|------|-----------|---------|-----------|---------|---------|
| eu-ai-act-2024-1689-en.pdf | EU AI Act | 2024/1689-original | 2026-03-19 | `bba630444b3278e881066774002a1d7824308934f49ccfa203e65be43692f55e` | Yes — source_quotes verbatim verified 2026-03-19 |

## Official Source URLs (for manual download)

| Regulation | Official URL | Format |
|-----------|-------------|--------|
| EU AI Act EN PDF | https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689 | PDF |
| EU AI Act EN HTML | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689 | HTML |
| EU AI Act (all languages) | https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng | ELI |
