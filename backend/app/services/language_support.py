"""
Multilingual text helpers for signals and evidence.

This module provides:
  1. Lightweight language detection without external dependencies
  2. RTL/LTR direction inference for rendering
  3. Translation-ready field normalization

Translation is intentionally pluggable. If no backend is configured,
non-English text is preserved in original form and marked as untranslated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

RTL_LANGUAGES = {"ar", "fa", "he", "ur"}

_ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
_HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF\u0590-\u08FF']+")

_STOPWORDS: dict[str, set[str]] = {
    "en": {"the", "and", "for", "with", "from", "attack", "military", "strike"},
    "es": {"el", "la", "los", "las", "de", "del", "por", "contra", "ataque"},
    "fr": {"le", "la", "les", "de", "des", "pour", "avec", "attaque"},
    "tr": {"ve", "bir", "ile", "icin", "askeri", "saldiri", "hava", "kuvvetleri"},
    "ru": {"и", "в", "на", "с", "военный", "удар", "атака"},
    "uk": {"і", "в", "на", "з", "військовий", "удар", "атака"},
    "ar": {"في", "من", "على", "ضربة", "هجوم", "عسكري"},
    "fa": {"در", "از", "به", "حمله", "نظامی", "موشکی"},
}

_LANGUAGE_NAMES = {
    "ar": "Arabic",
    "en": "English",
    "es": "Spanish",
    "fa": "Farsi",
    "fr": "French",
    "he": "Hebrew",
    "ru": "Russian",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "und": "Unknown",
}


@dataclass(frozen=True)
class MultilingualTextFields:
    """Normalized multilingual payload fields for text-bearing records."""

    language: str
    language_name: str
    text_direction: str
    translation_status: str
    title_original: str
    description_original: str
    title_translated: str | None
    description_translated: str | None

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return asdict(self)


class TranslationService:
    """Simple translation service abstraction.

    The current implementation is deliberately conservative: it only marks
    text as translatable and accepts caller-provided translations. A real
    machine translation backend can replace this later without changing the
    shape of stored data.
    """

    def __init__(self) -> None:
        self._backend = settings.translation_backend.strip().lower()
        self._warned = False

    def translate_fields(
        self,
        *,
        source_language: str,
        title: str,
        description: str,
        translated_title: str | None = None,
        translated_description: str | None = None,
    ) -> tuple[str, str | None, str | None]:
        """Return translation status plus translated text fields."""
        target = normalize_language_code(settings.translation_target_language) or "en"

        if translated_title or translated_description:
            return "provided", _clean_text(translated_title), _clean_text(translated_description)

        if source_language in ("", "und", target):
            return "not_needed", _clean_text(title) or None, _clean_text(description) or None

        if self._backend:
            if not self._warned:
                logger.warning(
                    "Translation backend '%s' configured but not implemented; storing original text only",
                    self._backend,
                )
                self._warned = True
            return "backend_unavailable", None, None

        return "untranslated", None, None


_translation_service = TranslationService()


def build_multilingual_text_fields(
    *,
    title: str | None,
    description: str | None,
    language_hint: str | None = None,
    translated_title: str | None = None,
    translated_description: str | None = None,
) -> MultilingualTextFields:
    """Normalize language, text direction, and translation-ready fields."""
    title_original = _clean_text(title)
    description_original = _clean_text(description)
    combined = " ".join(part for part in (title_original, description_original) if part)

    language = detect_language(combined, hint=language_hint)
    text_direction = "rtl" if is_rtl_language(language) else "ltr"
    translation_status, title_translated, description_translated = _translation_service.translate_fields(
        source_language=language,
        title=title_original,
        description=description_original,
        translated_title=translated_title,
        translated_description=translated_description,
    )

    return MultilingualTextFields(
        language=language,
        language_name=language_name(language),
        text_direction=text_direction,
        translation_status=translation_status,
        title_original=title_original,
        description_original=description_original,
        title_translated=title_translated,
        description_translated=description_translated,
    )


def normalize_language_code(value: str | None) -> str | None:
    """Normalize common language codes and names into short tags."""
    if not value:
        return None

    text = str(value).strip().lower().replace("_", "-")
    if not text:
        return None

    aliases = {
        "arabic": "ar",
        "ar-sa": "ar",
        "english": "en",
        "en-us": "en",
        "en-gb": "en",
        "farsi": "fa",
        "fa-ir": "fa",
        "persian": "fa",
        "french": "fr",
        "hebrew": "he",
        "russian": "ru",
        "spanish": "es",
        "turkish": "tr",
        "ukrainian": "uk",
    }
    if text in aliases:
        return aliases[text]

    return text.split("-", 1)[0]


def detect_language(text: str | None, *, hint: str | None = None) -> str:
    """Best-effort language detection for common conflict-monitoring languages."""
    normalized_hint = normalize_language_code(hint)
    if normalized_hint:
        return normalized_hint

    sample = _clean_text(text)
    if not sample:
        return "und"

    if _HEBREW_RE.search(sample):
        return "he"

    if _ARABIC_RE.search(sample):
        if any(ch in sample for ch in ("پ", "چ", "ژ", "گ", "ک", "ی")):
            return "fa"
        return "ar"

    if _CYRILLIC_RE.search(sample):
        if any(ch in sample.lower() for ch in ("і", "ї", "є", "ґ")):
            return "uk"
        return "ru"

    if _LATIN_RE.search(sample):
        words = {match.group(0).lower() for match in _WORD_RE.finditer(sample)}
        accent_text = sample.lower()

        if any(ch in accent_text for ch in ("ş", "ğ", "ı", "İ", "ç", "ö", "ü")):
            return "tr"
        if any(ch in accent_text for ch in ("¿", "¡", "ñ")):
            return "es"
        if any(ch in accent_text for ch in ("à", "â", "ç", "è", "é", "ê", "ë", "î", "ï", "ô", "ù", "û", "ü")):
            fr_score = len(words & _STOPWORDS["fr"])
            es_score = len(words & _STOPWORDS["es"])
            return "fr" if fr_score >= es_score else "es"

        best_language = "en"
        best_score = -1
        for language in ("en", "es", "fr", "tr"):
            score = len(words & _STOPWORDS[language])
            if score > best_score:
                best_language = language
                best_score = score

        return best_language if best_score > 0 else "en"

    return "und"


def is_rtl_language(language: str | None) -> bool:
    """Return True if a language is typically rendered RTL."""
    normalized = normalize_language_code(language)
    return normalized in RTL_LANGUAGES


def language_name(language: str | None) -> str:
    """Return a human-friendly language label."""
    normalized = normalize_language_code(language) or "und"
    return _LANGUAGE_NAMES.get(normalized, normalized.upper())


def _clean_text(value: str | None) -> str:
    """Normalize empty text values."""
    if value is None:
        return ""
    return str(value).strip()
