#!/usr/bin/env python3
"""Create an ephemeral source tree for the English build.

This pre-translation pass protects department-specific abbreviations before
DeepL sees them. The repository source files are never modified.
"""

from pathlib import Path
import shutil

ROOT = Path.cwd()
OUT = ROOT / ".i18n-source"

# Longer phrases first so the generic abbreviation does not break them.
PRETRANSLATION_OVERRIDES = [
    ("언홍원 최고위과정", "Executive Program"),
    ("언홍원", "JMC Grad School"),
]


def apply_overrides(text: str) -> str:
    for source, target in PRETRANSLATION_OVERRIDES:
        text = text.replace(source, target)
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)

    for src in ROOT.glob("*.html"):
        (OUT / src.name).write_text(
            apply_overrides(src.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    for src in (ROOT / "data").glob("*.json"):
        (OUT / "data" / src.name).write_text(
            apply_overrides(src.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    print(f"Prepared English translation source in {OUT}")


if __name__ == "__main__":
    main()
