#!/usr/bin/env python3
"""Build the English static site from the Korean GitHub Pages source.

The Korean root HTML remains the single structural source of truth. This script:
- copies selected pages into /en/ while preserving markup/classes/styles;
- translates Hangul-bearing visible text with DeepL;
- applies local terminology overrides before translation;
- rewrites local asset paths for the /en/ directory;
- removes Korean-only notices/equipment-rental navigation from English pages;
- generates localized research JSON feeds;
- adds canonical/hreflang metadata.

Usage (from repository root):
    python scripts/build_english_site.py --source . --output build/en \
        --cache .i18n-cache/en.json

Environment:
    DEEPL_API_KEY or DEEPL_AUTH_KEY  DeepL API key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

try:
    from bs4 import BeautifulSoup, Comment, NavigableString
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: beautifulsoup4") from exc

try:
    import deepl
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: deepl") from exc


BASE_URL = "https://comm.yonsei.ac.kr"
HANGUL_RE = re.compile(r"[가-힣]")

# Pages included in the first production English build.
# Korean-only notices, recruitment/competition notices, and equipment rental are omitted.
EN_PAGES = [
    "index.html",
    "intro.html",
    "people.html",
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

# These pages intentionally remain Korean-only in this phase.
OMITTED_EN_PAGES = {
    "notice.html",
    "jobnotice.html",
    "lend.html",
    # Deferred pending official English name/title review.
    "people_emeritus.html",
    "people_profpractice.html",
}

LOCALIZED_JSON = [
    "crisis_people.json",
    "digital_people.json",
    "health_people.json",
    "jds_people.json",
]

# User-confirmed official terminology + stable UI terminology.
# Longer phrases are applied first.
TERM_OVERRIDES = {
    "언론홍보영상학부": "Department of Communication",
    "학부장": "Department Head",
    "대학원 주임교수": "Graduate Program Chair",
    "언론홍보대학원": "Graduate School of Journalism and Mass Communication",
    "윤세영 저널리즘전공": "YSJ Program",
    "윤세영저널리즘전공": "YSJ Program",

    # Navigation / recurring UI labels.
    "학부소개": "About",
    "인사말": "Welcome",
    "학과연혁": "History",
    "주요시설안내": "Facilities",
    "찾아오시는길": "Directions",
    "구성원": "People",
    "현직교수": "Faculty",
    "학사안내": "Academics",
    "입학안내": "Admissions",
    "학사일정": "Academic Calendar",
    "교과과정": "Curriculum",
    "졸업요건": "Degree Requirements",
    "장학": "Scholarships",
    "복수전공/부전공": "Double Major / Minor",
    "교환학생/학점인정": "Exchange / Credit Transfer",
    "연구/국제": "Research & Global",
    "연구분야": "Research Areas",
    "연구소/대형센터": "Research Institutes / Centers",
    "일반대학원": "Graduate Program",
    "학석사연계": "Combined B.A./M.A. Program",
    "특수전문대학원": "Professional Graduate Programs",
    "언홍원 최고위과정": "Executive Program",
    "전체": "All",
}

# Strings in these elements are code/data rather than user-facing prose.
SKIP_PARENTS = {"script", "style", "code", "pre", "svg", "noscript", "template"}
TRANSLATABLE_ATTRS = ("alt", "title", "aria-label", "placeholder")


class TranslationCache:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        else:
            self.data = {}

    def get(self, text: str) -> str | None:
        return self.data.get(text)

    def set(self, text: str, translation: str) -> None:
        self.data[text] = translation

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class EnglishTranslator:
    def __init__(self, auth_key: str | None, cache: TranslationCache):
        self.cache = cache
        self.client = deepl.Translator(auth_key) if auth_key else None
        self.name_map: dict[str, str] = {"송현진": "Hyunjin Song"}

    def add_name_map(self, source_root: Path) -> None:
        for filename in LOCALIZED_JSON:
            path = source_root / "data" / filename
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            people = payload.get("people", []) if isinstance(payload, dict) else []
            for person in people:
                if not isinstance(person, dict):
                    continue
                ko = str(person.get("nameKo") or "").strip()
                en = str(person.get("nameEn") or "").strip()
                if ko and en:
                    self.name_map[ko] = en

    def preprocess(self, text: str) -> str:
        result = text
        replacements = {**TERM_OVERRIDES, **self.name_map}
        for src in sorted(replacements, key=len, reverse=True):
            result = result.replace(src, replacements[src])
        return result

    def needs_translation(self, text: str) -> bool:
        return bool(HANGUL_RE.search(text))

    def translate_many(self, texts: Iterable[str]) -> dict[str, str]:
        unique: list[str] = []
        seen: set[str] = set()
        direct: dict[str, str] = {}

        for original in texts:
            if original in seen:
                continue
            seen.add(original)
            prepared = self.preprocess(original)
            if not self.needs_translation(prepared):
                direct[original] = prepared
                continue
            cached = self.cache.get(prepared)
            if cached is not None:
                direct[original] = cached
            else:
                unique.append(original)

        if unique and self.client is None:
            sample = ", ".join(repr(x[:80]) for x in unique[:3])
            raise RuntimeError(
                "DeepL API key is required because uncached Korean strings remain. "
                f"Examples: {sample}"
            )

        # Keep requests comfortably below API payload limits.
        idx = 0
        while idx < len(unique):
            batch_original: list[str] = []
            batch_prepared: list[str] = []
            chars = 0
            while idx < len(unique) and len(batch_original) < 40:
                original = unique[idx]
                prepared = self.preprocess(original)
                if batch_original and chars + len(prepared) > 22000:
                    break
                batch_original.append(original)
                batch_prepared.append(prepared)
                chars += len(prepared)
                idx += 1

            results = self.client.translate_text(
                batch_prepared,
                source_lang="KO",
                target_lang="EN-US",
                preserve_formatting=True,
            )
            if not isinstance(results, list):
                results = [results]
            if len(results) != len(batch_original):
                raise RuntimeError("DeepL returned an unexpected number of translations")

            for original, prepared, result in zip(batch_original, batch_prepared, results):
                translated = result.text
                self.cache.set(prepared, translated)
                direct[original] = translated

        return direct

    def translate_one(self, text: str) -> str:
        return self.translate_many([text])[text]


def split_whitespace(text: str) -> tuple[str, str, str]:
    m = re.match(r"^(\s*)(.*?)(\s*)$", text, flags=re.S)
    assert m
    return m.group(1), m.group(2), m.group(3)


def collect_html_strings(soup: BeautifulSoup) -> tuple[list[tuple[NavigableString, str, str, str]], list[tuple[object, str, str]]]:
    nodes: list[tuple[NavigableString, str, str, str]] = []
    attrs: list[tuple[object, str, str]] = []

    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        parent_name = getattr(node.parent, "name", None)
        if parent_name in SKIP_PARENTS:
            continue
        leading, core, trailing = split_whitespace(str(node))
        if core and HANGUL_RE.search(core):
            nodes.append((node, leading, core, trailing))

    for tag in soup.find_all(True):
        if tag.name in SKIP_PARENTS:
            continue
        for attr in TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if isinstance(value, str) and HANGUL_RE.search(value):
                attrs.append((tag, attr, value))

    return nodes, attrs


def translate_html(soup: BeautifulSoup, translator: EnglishTranslator) -> None:
    nodes, attrs = collect_html_strings(soup)
    source_strings = [core for _, _, core, _ in nodes] + [value for _, _, value in attrs]
    translations = translator.translate_many(source_strings)

    for node, leading, core, trailing in nodes:
        node.replace_with(leading + translations[core] + trailing)

    for tag, attr, value in attrs:
        tag[attr] = translations[value]


def remove_english_omissions(soup: BeautifulSoup, page_name: str) -> None:
    # Remove the entire Notices dropdown from English navigation.
    for li in soup.select("li.nav-item.dropdown"):
        top_link = li.find("a", class_=lambda c: c and "nav-link" in c.split())
        if top_link and "공지사항" in top_link.get_text(" ", strip=True):
            li.decompose()

    # People pages deferred pending official English names/titles.
    for anchor in list(soup.find_all("a", href=True)):
        href_path = urlsplit(anchor["href"]).path
        target = Path(href_path).name
        if target in {"people_emeritus.html", "people_profpractice.html"}:
            parent_li = anchor.find_parent("li")
            if parent_li:
                parent_li.decompose()

    # Homepage: notices/equipment-rental cards are omitted. Balance the two remaining cards.
    if page_name == "index.html":
        for anchor in list(soup.select(".featured-block a[href]")):
            target = Path(urlsplit(anchor.get("href", "")).path).name
            if target in {"notice.html", "lend.html"}:
                col = anchor.find_parent("div", class_=re.compile(r"\bcol-(?:lg|md)-\d+\b"))
                if col:
                    col.decompose()
        # Expand the two academic cards to keep the original row visually balanced.
        for anchor in soup.select('.featured-block a[href="curriculum.html"], .featured-block a[href="curriculum_graduate.html"]'):
            col = anchor.find_parent("div", class_=re.compile(r"\bcol-lg-3\b"))
            if col:
                classes = list(col.get("class", []))
                col["class"] = ["col-lg-6" if c == "col-lg-3" else c for c in classes]


def rewrite_srcset(value: str, rewrite_url) -> str:
    chunks = []
    for part in value.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        bits[0] = rewrite_url(bits[0])
        chunks.append(" ".join(bits))
    return ", ".join(chunks)


def rewrite_paths(soup: BeautifulSoup) -> None:
    en_pages = set(EN_PAGES)

    def rewrite_url(value: str) -> str:
        if not value or value.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            return value
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return value
        if parsed.path.startswith("/"):
            return value

        path = parsed.path
        if not path:
            return value

        filename = Path(path).name
        # English pages remain peer-relative inside /en/.
        if filename in en_pages and path.endswith(".html"):
            new_path = filename
        # Localized research JSON is emitted inside /en/data/ and is referenced
        # from inline fetch() code, not HTML attributes. All ordinary data links
        # (PDF/HWP/etc.) should continue to point to the Korean/shared root data.
        elif path.startswith(("css/", "js/", "images/", "fonts/", "data/", "admin/", "config/")):
            new_path = "../" + path
        elif path.endswith(".html"):
            # Any non-English local HTML is deliberately not surfaced as an English page.
            new_path = "../" + path
        else:
            new_path = "../" + path

        return urlunsplit(("", "", new_path, parsed.query, parsed.fragment))

    for tag in soup.find_all(True):
        for attr in ("href", "src", "action", "poster"):
            if isinstance(tag.get(attr), str):
                tag[attr] = rewrite_url(tag[attr])
        if isinstance(tag.get("srcset"), str):
            tag["srcset"] = rewrite_srcset(tag["srcset"], rewrite_url)


def set_language_metadata(soup: BeautifulSoup, page_name: str) -> None:
    if soup.html:
        soup.html["lang"] = "en"

    head = soup.head
    if not head:
        return

    # Remove stale canonical/alternate entries before inserting deterministic ones.
    for link in list(head.find_all("link", rel=lambda v: v and ("canonical" in v or "alternate" in v))):
        link.decompose()

    ko_path = "/" if page_name == "index.html" else f"/{page_name}"
    en_path = "/en/" if page_name == "index.html" else f"/en/{page_name}"

    canonical = soup.new_tag("link", rel="canonical", href=BASE_URL + en_path)
    alt_ko = soup.new_tag("link", rel="alternate", hreflang="ko", href=BASE_URL + ko_path)
    alt_en = soup.new_tag("link", rel="alternate", hreflang="en", href=BASE_URL + en_path)
    alt_x = soup.new_tag("link", rel="alternate", hreflang="x-default", href=BASE_URL + ko_path)
    head.append(canonical)
    head.append(alt_ko)
    head.append(alt_en)
    head.append(alt_x)

    # Research data uses the English name only; hide the duplicate secondary name.
    if page_name.startswith("research_"):
        style = soup.new_tag("style")
        style.string = '[class*="profile-name-en"]{display:none!important}'
        head.append(style)


def localize_language_menu(soup: BeautifulSoup) -> None:
    # lang switcher JS performs navigation; update the English menu label state only.
    label = soup.select_one("#langSwitcher .lang-label")
    if label:
        label.string = "Language"

    # The current YSJ degree program should use the user-confirmed program name.
    # Historical references to the former journalism school are intentionally left
    # for normal translation rather than globally renamed.
    for anchor in soup.select('a[href*="/YSJ01.do"]'):
        anchor.string = "YSJ Program"


def translate_script_literals(soup: BeautifulSoup) -> None:
    # Dynamic research renderers contain a small number of Korean UI literals
    # inside JavaScript, which DeepL must never process as code.
    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string
        replacements = {
            ">전체</button>": ">All</button>",
            '"전체"': '"All"',
            "'전체'": "'All'",
        }
        new_text = text
        for src, dst in replacements.items():
            new_text = new_text.replace(src, dst)
        if new_text != text:
            script.string.replace_with(new_text)


def translate_json_value(value, translator: EnglishTranslator):
    if isinstance(value, dict):
        # Existing research feeds already contain authoritative English faculty names.
        # Keep nameEn and make nameKo render as the same English name so legacy JS can
        # retain its markup without structural divergence.
        result = {}
        for key, item in value.items():
            if key == "nameKo" and isinstance(value.get("nameEn"), str) and value.get("nameEn"):
                result[key] = value["nameEn"]
            elif key == "image" and isinstance(item, str) and item.startswith("images/"):
                result[key] = "../" + item
            else:
                result[key] = translate_json_value(item, translator)
        return result
    if isinstance(value, list):
        return [translate_json_value(item, translator) for item in value]
    if isinstance(value, str) and HANGUL_RE.search(value):
        return translator.translate_one(value)
    return value


def build_json_feeds(source_root: Path, output_root: Path, translator: EnglishTranslator) -> None:
    data_out = output_root / "data"
    data_out.mkdir(parents=True, exist_ok=True)
    for filename in LOCALIZED_JSON:
        src = source_root / "data" / filename
        if not src.exists():
            print(f"[warn] localized JSON source missing: {src}", file=sys.stderr)
            continue
        payload = json.loads(src.read_text(encoding="utf-8"))
        localized = translate_json_value(payload, translator)
        (data_out / filename).write_text(
            json.dumps(localized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def build_page(source_root: Path, output_root: Path, page_name: str, translator: EnglishTranslator) -> None:
    src = source_root / page_name
    if not src.exists():
        raise FileNotFoundError(src)

    # html.parser preserves the current page's structure sufficiently while avoiding
    # a build dependency on libxml2.
    soup = BeautifulSoup(src.read_text(encoding="utf-8"), "html.parser")

    # Structural changes must inspect Korean source labels before translation.
    remove_english_omissions(soup, page_name)
    translate_html(soup, translator)
    translate_script_literals(soup)
    rewrite_paths(soup)
    set_language_metadata(soup, page_name)
    localize_language_menu(soup)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / page_name).write_text(str(soup), encoding="utf-8")
    print(f"[en] {page_name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".", help="Repository source root")
    parser.add_argument("--output", default="build/en", help="English output directory")
    parser.add_argument("--cache", default=".i18n-cache/en.json", help="Translation cache file")
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    cache = TranslationCache(Path(args.cache).resolve())
    auth_key = os.environ.get("DEEPL_API_KEY") or os.environ.get("DEEPL_AUTH_KEY")
    translator = EnglishTranslator(auth_key, cache)
    translator.add_name_map(source_root)

    try:
        for page_name in EN_PAGES:
            build_page(source_root, output_root, page_name, translator)
        build_json_feeds(source_root, output_root, translator)
        cache.save()
    except Exception as exc:
        cache.save()
        print(f"English build failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
