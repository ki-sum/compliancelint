# ComplianceLint — EU AI Act Compliance Engine

Open-source, MCP-native compliance engine that decomposes EU AI Act requirements into machine-readable obligations. Each obligation is classified into one of three layers: code-verifiable (direct scanner detection), hybrid (AI-assisted evidence collection), or human-only (structured attestation). The scanner handles the first layer directly and feeds evidence into the latter two.

## Architecture

```
core/             — Protocol definitions, ObligationEngine, persistence layer
modules/          — Per-article scanning modules (44 modules; Art. 4a has permissions only, no module)
obligations/      — Legal obligation definitions (248 obligations, 45 articles incl. Art. 4a)
server.py         — MCP Server entry point (14 tools)
```

## Status

- [x] MCP Server with 14 tools
- [x] 44 article modules (Art. 4–6, 8–27, 41, 43, 47, 49–55, 60, 61, 71–73, 80, 82, 86, 91, 92, 111)
- [x] 248 legal obligations — verified against EUR-Lex source text on all 45 articles
- [x] Persistence layer (`.compliancelint/` per-project scan state)
- [x] Unit + server integration tests (100% pass rate)
