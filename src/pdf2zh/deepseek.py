from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import requests

SYSTEM_PROMPT = """Translate English or Spanish document text into concise Simplified Chinese.
Return JSON only. Preserve numbers, units, acronyms, names, section numbers, formulas, and placeholders.
Prefer compact wording suitable for the original PDF text box. Do not add explanations."""
CACHE_VERSION = "deepseek-chat-layout-v1"
DOCUMENT_ERROR_REPLACEMENTS = {
    "¡Error! Marcador no definido.": "错误！未定义书签。",
    "Error! Bookmark not defined.": "错误！未定义书签。",
    "Error! Reference source not found.": "错误！未找到引用源。",
}
FIXED_HEADING_TRANSLATIONS = {
    "índice de tablas": "表格目录",
    "indice de tablas": "表格目录",
    "list of tables": "表格目录",
    "índice de figuras": "图目录",
    "indice de figuras": "图目录",
    "índice de gráficos": "图目录",
    "indice de graficos": "图目录",
    "list of figures": "图目录",
}


def normalize_translation(text: str) -> str:
    normalized = text
    for source, replacement in DOCUMENT_ERROR_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)
    return normalized


def fixed_translation(text: str) -> str | None:
    compact = " ".join(text.split()).casefold()
    return FIXED_HEADING_TRANSLATIONS.get(compact)


class DeepSeekTranslator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        cache_path: str | Path | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY environment variable.")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = (
            base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache: dict[str, str] = {}
        if self.cache_path and self.cache_path.exists():
            loaded = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"Invalid translation cache: {self.cache_path}")
            self.cache = {str(key): str(value) for key, value in loaded.items()}

    def _cache_key(self, source_language: str, text: str) -> str:
        return f"{CACHE_VERSION}|{self.model}|{source_language}|zh|{text}"

    def _save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_name(
                f"{self.cache_path.name}.{uuid.uuid4().hex}.tmp"
            )
            temporary.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.cache_path)

    def translate_batch(self, texts: list[str], source_language: str) -> list[str]:
        results = [""] * len(texts)
        missing: list[tuple[int, str]] = []
        for index, text in enumerate(texts):
            fixed = fixed_translation(text)
            if fixed is not None:
                results[index] = fixed
                continue
            key = self._cache_key(source_language, text)
            if key in self.cache:
                results[index] = normalize_translation(self.cache[key])
            else:
                missing.append((index, text))
        if not missing:
            return results

        prompt = (
            f"Source language: {source_language}. Translate each item to Simplified Chinese. "
            "Return an object with a translations array; each item must contain id and translation.\n"
            + json.dumps(
                [{"id": index, "text": text} for index, text in missing],
                ensure_ascii=False,
            )
        )
        translated_by_id = None
        for attempt in range(4):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=120,
                )
                if not response.ok:
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        response.raise_for_status()
                    raise RuntimeError(f"DeepSeek temporary HTTP error: {response.status_code}")
                content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                items = parsed.get("translations", parsed.get("items", []))
                candidate = {
                    int(item["id"]): str(item["translation"]).strip()
                    for item in items
                    if str(item.get("translation", "")).strip()
                }
                expected_ids = {index for index, _ in missing}
                if set(candidate) != expected_ids:
                    raise ValueError(
                        f"DeepSeek returned ids {sorted(candidate)}; "
                        f"expected {sorted(expected_ids)}."
                    )
                translated_by_id = candidate
                break
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                raise RuntimeError(f"DeepSeek HTTP error: {status}") from exc
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, requests.RequestException, RuntimeError):
                if attempt == 3:
                    raise RuntimeError("DeepSeek returned an invalid response after retries.")
            time.sleep(2**attempt)
        if translated_by_id is None:
            raise RuntimeError("DeepSeek request failed after retries.")
        for index, text in missing:
            translated = normalize_translation(translated_by_id[index])
            results[index] = translated
            self.cache[self._cache_key(source_language, text)] = translated
        self._save_cache()
        return results
