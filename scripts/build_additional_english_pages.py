#!/usr/bin/env python3
"""Build English pages that are deliberately managed outside the core page list."""

import argparse
import os
from pathlib import Path

from build_english_site import TranslationCache, EnglishTranslator, build_page

ADDITIONAL_PAGES = ["people_emeritus.html"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".")
    parser.add_argument("--output", default="build/en")
    parser.add_argument("--cache", default=".i18n-cache/en.json")
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    cache = TranslationCache(Path(args.cache).resolve())
    auth_key = os.environ.get("DEEPL_API_KEY") or os.environ.get("DEEPL_AUTH_KEY")
    translator = EnglishTranslator(auth_key, cache)
    translator.add_name_map(source_root)

    try:
        for page_name in ADDITIONAL_PAGES:
            build_page(source_root, output_root, page_name, translator)
        cache.save()
    except Exception as exc:
        cache.save()
        print(f"Additional English-page build failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
