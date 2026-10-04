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


def soup_for(path: Path) -> BeautifulSoup:
    return BeautifulSoup(text(path), "html.parser")


def verify_korean() -> None:
    soup = soup_for(BUILD / "index.html")
    require(soup.html and soup.html.get("lang") == "ko", "Korean index must declare lang=ko")
    toggle = soup.select_one("#langSwitcher .lang-direct-toggle")
    require(toggle is not None, "Korean index must contain the direct EN toggle")
    require(toggle.get_text(" ", strip=True).startswith("EN"), "Korean toggle must display EN")
    require(toggle.get("href") == "en/", "Korean index EN toggle must point to en/")


def verify_intro() -> None:
    soup = soup_for(EN / "intro.html")
    block = soup.select_one(".about-section .custom-text-block")
    require(block is not None, "English intro missing welcome block")
    require(block.find("h2") and block.find("h2").get_text(" ", strip=True) == "Welcome", "Intro heading must be Welcome")
    subtitle = block.find("p", class_=lambda c: c and "text-muted" in c.split())
    require(subtitle is not None, "Intro missing Department Head subtitle")
    require(subtitle.get_text(" ", strip=True) == "Department Head | Hyunjin Song", "Intro subtitle must be Department Head | Hyunjin Song")

    intro_text = block.get_text(" ", strip=True)
    forbidden = [
        "The Department of Communication at Yonsei University",
        "Department of Communication at Yonsei University",
        "Yonsei University's Department of Communication",
        "Yonsei University’s Department of Communication",
        "Yonsei University Department of Communication",
    ]
    for phrase in forbidden:
        require(phrase not in intro_text, f"Intro should use We/The Department instead of: {phrase}")


def verify_people() -> None:
    soup = soup_for(EN / "people.html")
    value = soup.get_text(" ", strip=True)

    required = [
        "JMC YSJ Program Chair",
        "Dean, Graduate School of Journalism & Mass Communication",
        "JMC Associate Dean & PR/Advertising Program Chair",
        "JMC Broadcasting/Media Content Program Chair",
        "Digital Platforms",
        "Journalism",
        "AI & Platform Media",
        "Neuroscience",
        "Political Communication",
    ]
    for item in required:
        require(item in value, f"English people page missing fixed copy: {item}")

    forbidden = [
        "Associate Dean, Graduate School of Journalism & Mass Communication; JMC PR/Advertising Program Chair",
        "JMC Broadcasting/Visual Media/Cultural Content Program Chair",
        "Digital Platforms | AI | Political Communication",
        "Journalism | Content Analysis | International Communication",
        "AI & Platform Media | Digital Cities | Risk Society & Polarization",
        "Neuroscience | Inner Communication | Communication Competence",
    ]
    for item in forbidden:
        require(item not in value, f"English people page contains obsolete copy: {item}")

    require("page-people-en" in soup.body.get("class", []), "People page missing English typography class")


def verify_curriculum(page_name: str) -> None:
    soup = soup_for(EN / page_name)
    require("page-curriculum-en" in soup.body.get("class", []), f"{page_name} missing English curriculum typography class")
    section = soup.select_one("#graduation-requirement")
    require(section is not None, f"{page_name} missing Degree Requirements section")
    wrap = section.select_one(".col-12.text-center")
    require(wrap is not None, f"{page_name} missing Degree Requirements heading wrapper")
    h2 = wrap.find("h2")
    require(h2 is not None and h2.get_text(" ", strip=True) == "Degree Requirements", f"{page_name} must show only Degree Requirements as heading")
    require(wrap.find("h5") is None, f"{page_name} Degree Requirements subtitle must be removed")


def verify_english() -> None:
    for page in REQUIRED_EN_PAGES:
        soup = soup_for(EN / page)
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
        "JMC Grad School",
    ]:
        require(required in index, f"English index missing fixed copy: {required}")

    verify_intro()
    verify_people()
    verify_curriculum("curriculum.html")
    verify_curriculum("curriculum_graduate.html")

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
    css = text(BUILD / "css" / "en.css")
    require("page-people-en" in css, "English CSS missing people-page typography override")
    require("page-curriculum-en" in css, "English CSS missing curriculum typography override")
    require((BUILD / "css" / "language-toggle.css").is_file(), "Missing css/language-toggle.css")
    verify_korean()
    verify_english()
    verify_no_google_translate()
    print("i18n production verification passed")


if __name__ == "__main__":
    main()
