# ComplianceLint — EU AI Act Compliance Engine

Open-source, MCP-native compliance engine that decomposes EU AI Act requirements into machine-readable obligations and maps them to automated code checks.

## Architecture

```
core/             — Protocol definitions, ObligationEngine, persistence layer
modules/          — Per-article scanning modules (10 articles covered)
obligations/      — Legal obligation definitions (94 obligations)
server.py         — MCP Server entry point (19 tools)
```

## Status

- [x] MCP Server with 19 tools
- [x] 10 article modules (Art. 5, 6, 9, 10, 11, 12, 13, 14, 15, 50)
- [x] 94 legal obligations — verified against EUR-Lex source text on all 10 articles
- [x] Persistence layer (`.compliancelint/` per-project scan state)
- [x] 560 tests passing (unit + server integration)
