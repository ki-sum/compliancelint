# ComplianceLint — EU AI Act Compliance Engine

Open-source, MCP-native compliance engine that decomposes EU AI Act requirements into machine-readable obligations and maps them to automated code checks.

## Architecture

```
core/             — Protocol definitions, ObligationEngine, persistence layer
modules/          — Per-article scanning modules (44 articles covered)
obligations/      — Legal obligation definitions (247 obligations)
server.py         — MCP Server entry point (19 tools)
```

## Status

- [x] MCP Server with 19 tools
- [x] 44 article modules (Art. 4–6, 8–27, 41, 43, 47, 49–55, 60, 61, 71–73, 80, 82, 86, 91, 92, 111)
- [x] 247 legal obligations — verified against EUR-Lex source text on all 44 articles
- [x] Persistence layer (`.compliancelint/` per-project scan state)
- [x] Unit + server integration tests (100% pass rate)
