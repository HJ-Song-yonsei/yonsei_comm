#!/usr/bin/env python3
"""Fail the Pages build when the Korean/English deployment contract is broken."""

from pathlib import Path
from bs4 import BeautifulSoup

BUILD = Path("build")
EN = BUILD / "en"

REQUIRED_EN_PAGES = [
    "index.html",
    "intro.html",
    "people.html",
    "people_emeritus.html",
    "curriculum.html",
    "curriculum_graduate.html",
    "scholarship.html",
    "research.html",
    "research_CnSC.html",
    "research_DPnAI.html",
    "research_JDnS.html",
    "research_PHnW.html",
    "research_institute.html",
    "yonsei_uva.html",
    "yonsei_cityu.html",
]

REQUIRED_JSON = [
    "crisis_people.json",
    "digital_people.json",
    "health_people.json",
    "jds_people.json",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text(path: Path) -> str:
    require(path.is_file(), f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def verify_korean() -> None:
    html = text(BUILD / "index.html")
    soup = BeautifulSoup(html, "html.parser")
    require(soup.html and soup.html.get("lang") == "ko", "Korean index must declare lang=ko")
    toggle = soup.select_one("#langSwitcher .lang-direct-toggle")
    require(toggle is not None, "Korean index must contain the direct EN toggle")
    require(toggle.get_text(" ", strip=True).startswith("EN"), "Korean toggle must display EN")
    require(toggle.get("href") == "en/", "Korean index EN toggle must point to en/")


def verify_english() -> None:
    for page in REQUIRED_EN_PAGES:
        html = text(EN / page)
        soup = BeautifulSoup(html, "html.parser")
        require(soup.html and soup.html.get("lang") == "en", f"{page} must declare lang=en")
        require(soup.select_one("#langSwitcher .lang-direct-toggle") is not None, f"{page} missing KO toggle")

    for name in REQUIRED_JSON:
        require((EN / "data" / name).is_file(), f"Missing localized data feed: {name}")

    index = text(EN / "index.html")
    for required in [
        "Grounded in empathy, a future opened by creativity",
        "Moving the world through persuasion and messages",
        "Global Media Studio",
        "Virtual Reality Lab",
        "Research Centers",
        "Line 2",
        "Gyeongui",
        "Undergraduate",
        "Graduate Program",
    ]:
        require(required in index, f"English index missing fixed copy: {required}")

    people = text(EN / "people.html")
    for required in [
        "JMC YSJ Program Chair",
        "Dean, Graduate School of Journalism &amp; Mass Communication",
        "Associate Dean, Graduate School of Journalism &amp; Mass Communication; JMC PR/Advertising Program Chair",
        "AI &amp; Platform Media | Digital Cities | Risk Society &amp; Polarization",
        "Neuroscience | Inner Communication | Communication Competence",
    ]:
        require(required in people, f"English people page missing fixed copy: {required}")

    combined = "\n".join(text(EN / page) for page in REQUIRED_EN_PAGES)
    for forbidden in [
        'href="notice.html"',
        'href="jobnotice.html"',
        'href="lend.html"',
        'href="people_profpractice.html"',
        'href="../notice.html"',
        'href="../jobnotice.html"',
        'href="../lend.html"',
        'href="../people_profpractice.html"',
    ]:
        require(forbidden not in combined, f"English build contains forbidden link: {forbidden}")


def verify_no_google_translate() -> None:
    candidates = list(BUILD.glob("*.html")) + list(EN.glob("*.html")) + [BUILD / "js" / "langswitcher.js"]
    for path in candidates:
        if not path.is_file():
            continue
        value = path.read_text(encoding="utf-8")
        require("translate.google.com" not in value, f"Google Translate loader remains in {path}")
        require("google_translate_element" not in value, f"Google Translate widget remains in {path}")


def main() -> None:
    require((BUILD / "css" / "en.css").is_file(), "Missing css/en.css")
    require((BUILD / "css" / "language-toggle.css").is_file(), "Missing css/language-toggle.css")
    verify_korean()
    verify_english()
    verify_no_google_translate()
    print("i18n production verification passed")


if __name__ == "__main__":
    main()
