#!/usr/bin/env python3
"""Prepare the Korean static pages for deployment.

The source HTML remains unchanged in structure. This deployment-stage pass:
- declares Korean pages as lang=ko;
- replaces the legacy Google Translate menu with a direct EN toggle;
- adds the shared language-toggle stylesheet;
- adds canonical/hreflang metadata where an English counterpart exists.
"""

from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

ROOT = Path("build")
BASE_URL = "https://comm.yonsei.ac.kr"

ENGLISH_PAGES = {
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
}


def english_target(page_name: str) -> str:
    if page_name == "index.html":
        return "en/"
    if page_name in ENGLISH_PAGES:
        return f"en/{page_name}"
    if page_name == "people_profpractice.html":
        return "en/people.html"
    return "en/"


def absolute_ko(page_name: str) -> str:
    return BASE_URL + ("/" if page_name == "index.html" else f"/{page_name}")


def absolute_en(page_name: str) -> str | None:
    if page_name not in ENGLISH_PAGES:
        return None
    return BASE_URL + ("/en/" if page_name == "index.html" else f"/en/{page_name}")


def ensure_stylesheet(soup: BeautifulSoup) -> None:
    if not soup.head:
        return
    if soup.find("link", href="css/language-toggle.css"):
        return
    link = soup.new_tag("link", rel="stylesheet", href="css/language-toggle.css")
    soup.head.append(link)


def replace_language_control(soup: BeautifulSoup, page_name: str) -> None:
    switcher = soup.select_one("#langSwitcher")
    if not switcher:
        return

    switcher.clear()
    link = soup.new_tag("a", href=english_target(page_name))
    link["class"] = ["lang-direct-toggle"]
    link["aria-label"] = "Switch to English"

    label = soup.new_tag("span")
    label.string = "EN"
    link.append(label)

    caret = soup.new_tag("span")
    caret["class"] = ["lang-direct-toggle-caret"]
    caret["aria-hidden"] = "true"
    caret.string = "▾"
    link.append(caret)
    switcher.append(link)

    for widget in list(soup.select("#google_translate_element")):
        widget.decompose()


def set_metadata(soup: BeautifulSoup, page_name: str) -> None:
    if soup.html:
        soup.html["lang"] = "ko"
    if not soup.head:
        return

    for link in list(soup.find_all("link", rel=lambda value: value and ("canonical" in value or "alternate" in value))):
        link.decompose()

    canonical = soup.new_tag("link", rel="canonical", href=absolute_ko(page_name))
    soup.head.append(canonical)

    en_url = absolute_en(page_name)
    if en_url:
        alt_ko = soup.new_tag("link", rel="alternate", hreflang="ko", href=absolute_ko(page_name))
        alt_en = soup.new_tag("link", rel="alternate", hreflang="en", href=en_url)
        alt_x = soup.new_tag("link", rel="alternate", hreflang="x-default", href=absolute_ko(page_name))
        soup.head.extend([alt_ko, alt_en, alt_x])


def process(path: Path) -> None:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    page_name = path.name
    set_metadata(soup, page_name)
    ensure_stylesheet(soup)
    replace_language_control(soup, page_name)
    path.write_text(str(soup), encoding="utf-8")


def main() -> None:
    for path in sorted(ROOT.glob("*.html")):
        if path.name == "people_backup.html":
            continue
        process(path)
        print(f"[ko] {path.name}")


if __name__ == "__main__":
    main()
