from __future__ import annotations

import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}


def translate_zh(text: str, dest: str = "ru") -> str:
    """Translate Chinese text to Russian (or another language)."""
    if not text or not text.strip():
        return ""

    if text in _cache:
        return _cache[text]

    try:
        translator = GoogleTranslator(source="zh-CN", target=dest)
        result = translator.translate(text)
        if result:
            _cache[text] = result
            return result
    except Exception as exc:
        logger.warning("Translation failed: %s", exc)

    return text


def translate_list(texts: list[str], dest: str = "ru") -> list[str]:
    """Translate a list of strings, batching into one request."""
    if not texts:
        return []

    # Check cache first
    result = []
    uncached = []
    uncached_indices = []
    for i, t in enumerate(texts):
        if t in _cache:
            result.append(_cache[t])
        else:
            uncached.append(t)
            uncached_indices.append(i)
            result.append(t)

    if not uncached:
        return result

    # Batch translate
    try:
        translator = GoogleTranslator(source="zh-CN", target=dest)
        batch = "\n".join(uncached)
        translated = translator.translate(batch)
        if translated:
            lines = translated.split("\n")
            for idx, line in zip(uncached_indices, lines):
                result[idx] = line.strip()
                _cache[uncached[uncached_indices.index(idx)]] = line.strip()
    except Exception as exc:
        logger.warning("Batch translation failed: %s", exc)

    return result
