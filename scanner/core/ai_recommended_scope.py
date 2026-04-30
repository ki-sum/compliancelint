"""Phase 6 Task 16 — `_ai_recommended_scope` builder.

Spec: 2026-04-29-pre-launch-paid-engine-spec §H "AI-First Onboarding".

Pure function that turns the cl_analyze_project metadata (manifest
contents + file extension counts) into a structured scaffolding
the AI client uses to:

  1. Classify the AI system (risk_classification, Annex III hits)
  2. Render a user-facing summary
  3. Ask "Continue scan? (y/n)" before chaining cl_scan_all

The scanner side does NO AI inference — it only extracts indicators
(string-match against a curated registry) and provides a renderable
template + instruction string. The AI client supplies the judgment.

Indicator buckets:

  - frameworks:          web / app frameworks (FastAPI, React, Spring,
                         ...). High-signal for project-type classification.
  - ai_libraries:        ML/AI libs (transformers, torch, openai, ...).
                         Triggers Art 51-55 GPAI consideration.
  - biometric_libraries: Annex III §1 trigger (face_recognition, dlib,
                         mediapipe, ...). Separated so AI client can flag
                         high-risk biometric identification without
                         conflating with generic AI lib presence.
  - languages:           inferred from file extensions (already counted
                         by analyze_project_metadata).

Lists are ALWAYS lists (never None / null) — AI clients iterate.
Empty project = empty lists.
"""
from __future__ import annotations

from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Curated indicator registry — kept deliberately small. The point is
# 80%-coverage of common stacks, not exhaustiveness. Extending later
# is cheap.
# ──────────────────────────────────────────────────────────────────────


_FRAMEWORKS = frozenset({
    # Python web/app frameworks
    "fastapi",
    "django",
    "flask",
    "tornado",
    "starlette",
    "aiohttp",
    "sanic",
    "bottle",
    "pyramid",
    # JS/TS frameworks
    "react",
    "vue",
    "angular",
    "svelte",
    "next",
    "nuxt",
    "remix",
    "express",
    "koa",
    "fastify",
    "nestjs",
    "hapi",
    # JVM
    "spring",
    "springboot",
    "spring-boot",
    "quarkus",
    "micronaut",
    # Go
    "gin",
    "echo",
    "fiber",
    "chi",
    # Ruby
    "rails",
    "sinatra",
    # PHP
    "laravel",
    "symfony",
    # Rust
    "rocket",
    "actix",
    "actix-web",
    "axum",
})


_AI_LIBRARIES = frozenset({
    # Foundation model SDKs
    "openai",
    "anthropic",
    "google-generativeai",
    "cohere",
    "mistralai",
    "ollama",
    "groq",
    # Frameworks
    "langchain",
    "langchain-core",
    "langchain-community",
    "llamaindex",
    "llama-index",
    "haystack",
    "instructor",
    "dspy",
    "guidance",
    # Model libraries
    "transformers",
    "sentence-transformers",
    "accelerate",
    "peft",
    "bitsandbytes",
    "diffusers",
    "vllm",
    "huggingface_hub",
    "huggingface-hub",
    # Inference engines / training
    "torch",
    "pytorch",
    "tensorflow",
    "tensorflow-cpu",
    "tensorflow-gpu",
    "jax",
    "flax",
    "scikit-learn",
    "sklearn",
    "xgboost",
    "lightgbm",
    "catboost",
    # Vector DBs
    "pinecone",
    "pinecone-client",
    "weaviate-client",
    "chromadb",
    "qdrant-client",
    "milvus",
    "faiss",
    "faiss-cpu",
    # Tokenizers / utilities
    "tiktoken",
    "tokenizers",
    "spacy",
    # JS-side AI
    "@anthropic-ai/sdk",
    "@google/generative-ai",
    "@langchain/core",
    "@langchain/community",
    "@huggingface/inference",
    "ai",  # Vercel AI SDK
})


# Annex III §1 — biometric identification triggers high-risk classification
# when used in publicly-accessible spaces. Separated from ai_libraries so
# AI client can flag this specifically.
_BIOMETRIC_LIBRARIES = frozenset({
    "face_recognition",
    "face-recognition",
    "facenet-pytorch",
    "dlib",
    "mediapipe",
    "deepface",
    "insightface",
    "retinaface",
    "retina-face",
    "opencv-python",  # often used for biometric capture, though not exclusively
    "opencv-contrib-python",
})


_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".m": "objective-c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
}


_USER_FACING_TEMPLATE = (
    "Detected: {stack}\n"
    "AI judgment: {risk} (confidence: {confidence})\n"
    "Scope estimate: {scope}\n"
    "Note: This is AI estimation. For SaaS-confirmed narrowing, connect to Starter+.\n"
    "Continue scan? (y/n)"
)


_INSTRUCTIONS = (
    "Read the detected_indicators above. Classify this AI system using "
    "EU AI Act categories: prohibited (Art 5), high-risk (Art 6 + Annex "
    "III), limited-risk (Art 50 transparency), or minimal-risk. "
    "Biometric libraries trigger Annex III §1 review if used in publicly-"
    "accessible spaces. Render the user_facing_summary_template, fill the "
    "{stack}/{risk}/{confidence}/{scope} placeholders, and ask the user "
    "y/n BEFORE calling cl_scan_all."
)


# ──────────────────────────────────────────────────────────────────────
# Extraction
# ──────────────────────────────────────────────────────────────────────


def _normalize_token(s: str) -> str:
    """Lowercase + strip whitespace + remove version specifiers.

    Examples:
        'FastAPI==0.100' → 'fastapi'
        'react@18.0.0'   → 'react'
        '"transformers"' → 'transformers'
    """
    s = s.strip().strip('"').strip("'").lower()
    # Strip everything after a version-spec separator. Order matters:
    # check '==' before '=' (etc).
    for sep in ("==", ">=", "<=", "~=", "!=", "@", ">", "<", "=", ":", ";", " "):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
    return s


def _tokens_from_text(text: str) -> set[str]:
    """Pull candidate package tokens from a manifest-text blob.

    Heuristic: split on common delimiters, strip version specs, return
    the deduped lowercase set. False positives are fine — they get
    filtered against the curated registries below.
    """
    if not text:
        return set()
    # Split on whitespace + common JSON/TOML delimiters.
    raw_tokens = []
    for line in text.splitlines():
        # Keep going through commas, colons, brackets — they all
        # separate package names in JSON deps / TOML tables / etc.
        for chunk in line.replace(",", " ").replace(":", " ").replace("[", " ").replace(
            "]", " "
        ).replace("{", " ").replace("}", " ").split():
            raw_tokens.append(chunk)
    return {_normalize_token(t) for t in raw_tokens if t}


def _extract_indicators_from_configs(config_contents: dict) -> dict:
    """Scan all manifest contents for known framework / AI / biometric libs."""
    all_tokens: set[str] = set()
    for _path, text in (config_contents or {}).items():
        if not isinstance(text, str):
            continue
        all_tokens |= _tokens_from_text(text)

    return {
        "frameworks": sorted(all_tokens & _FRAMEWORKS),
        "ai_libraries": sorted(all_tokens & _AI_LIBRARIES),
        "biometric_libraries": sorted(all_tokens & _BIOMETRIC_LIBRARIES),
    }


def _extract_languages_from_file_types(file_types: dict) -> list[str]:
    """Map extension → language from analyze_project_metadata's
    file_types counter. Return sorted unique list."""
    if not file_types:
        return []
    langs: set[str] = set()
    for ext in file_types.keys():
        lang = _EXT_TO_LANG.get(ext.lower())
        if lang:
            langs.add(lang)
    return sorted(langs)


def build_ai_recommended_scope(
    metadata: dict,
    tier_at_scan: Optional[str] = None,
) -> dict:
    """Build the `_ai_recommended_scope` field for cl_analyze_project.

    Args:
        metadata: the dict returned by `analyze_project_metadata`
          (must have `config_contents` and `file_types` at minimum).
        tier_at_scan: cached tier for upgrade-warning copy. None /
          "" → "unconnected".

    Returns:
        Structured scaffolding the AI client uses to render the
        user-facing summary and chain cl_scan_all. NEVER None.
        Lists are always lists, never null.
    """
    config_contents = metadata.get("config_contents") or {}
    file_types = metadata.get("file_types") or {}

    indicators_from_configs = _extract_indicators_from_configs(config_contents)
    languages = _extract_languages_from_file_types(file_types)

    detected_indicators = {
        "frameworks": indicators_from_configs["frameworks"],
        "ai_libraries": indicators_from_configs["ai_libraries"],
        "biometric_libraries": indicators_from_configs["biometric_libraries"],
        "languages": languages,
    }

    return {
        "detected_indicators": detected_indicators,
        "confirmation_required": True,
        "tier_at_scan": tier_at_scan or "unconnected",
        "user_facing_summary_template": _USER_FACING_TEMPLATE,
        "ai_classification_instructions": _INSTRUCTIONS,
    }
