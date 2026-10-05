#!/usr/bin/env python3
"""Apply deterministic English terminology, people metadata, and page-specific refinements."""

from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, NavigableString

ROOT = Path("build/en")

PEOPLE = {
    "taewookang.jpg": {"name": "Taewoo Kang", "fields": "Digital Platforms"},
    "kkmo.jpg": {"name": "Kyoungmo Kim", "role": "JMC YSJ Program Chair", "fields": "Journalism"},
    "yckim.jpg": {"name": "Yong-Chan Kim", "role": "Vice President for International Affairs", "fields": "AI & Platform Media"},
    "jrkim.jpg": {"name": "Jarim Kim", "fields": "Risk & Crisis Communication"},
    "jkim.jpg": {"name": "Joohan Kim", "fields": "Neuroscience"},
    "Namkee_Park.jpg": {"name": "Namkee Park", "role": "Dean, Graduate School of Journalism & Mass Communication", "fields": "New Media Technology"},
    "ymbaek.jpg": {"name": "Young Min Baek", "fields": "Political Communication"},
    "jpaek.jpg": {"name": "Jihyun Paik", "fields": "Interpersonal Communication"},
    "ymsang.jpg": {"name": "Yoonmo Sang", "role": "JMC Journalism Program Chair", "fields": "Media Law"},
    "yhsung.jpg": {"name": "Yoonhee Sung", "role": "JMC Associate Dean & PR/Advertising Program Chair", "fields": "Advertising & Media Technology"},
    "jso.jpg": {"name": "Jiyeon So", "role": "Graduate Program Chair", "fields": "Health Communication"},
    "hyunjinsong.jpg": {"name": "Hyunjin Song", "role": "Department Head", "fields": "Political Communication"},
    "larosa.jpg": {"name": "Nayeon Lee", "fields": "Journalism Principles"},
    "sylee.jpg": {"name": "Sang Yup Lee", "fields": "Computational Social Science"},
    "ccho.jpg": {"name": "Chang-Hoan Cho", "fields": "Digital Advertising"},
    "sychoi3.jpg": {"name": "Seokyoung Choi", "role": "JMC Broadcasting/Media Content Program Chair", "fields": "Communication Technology"},
}

# Historical spellings are curated rather than machine-transliterated.
EMERITUS = {
    "sjw.jpg": "Joung-Woo Suh",
    "kys.jpg": "Young Seok Kim",
    "cys.png": "Yang Soo Choi",
    "yyc.jpg": "Young-Chul Yoon",
    "ksh.jpg": "Sang Hyun Kang",
    "phs.png": "Heong-Soo Park",
    "cjh.png": "Joung-Ho Choi",
    "oih.png": "In-Hwan Oh",
    "default02.jpg": "Sang-Hoe Lee",
    "hjh.png": "Jung Ho Han",
    "khj.png": "Hee-Jin Kim",
}


def set_text(tag, text):
    if tag is None:
        return
    tag.clear()
    tag.append(text)


def add_body_class(soup, name):
    if not soup.body:
        return
    classes = list(soup.body.get("class", []))
    if name not in classes:
        classes.append(name)
    soup.body["class"] = classes


def inject_stylesheets(soup):
    if not soup.head:
        return
    for href in ("../css/en.css", "../css/language-toggle.css"):
        if not soup.find("link", href=href):
            soup.head.append(soup.new_tag("link", rel="stylesheet", href=href))


def fix_brand(soup):
    span = soup.select_one(".navbar-brand span")
    if not span:
        return
    for child in list(span.contents):
        if isinstance(child, NavigableString) and child.strip():
            child.extract()
    small = span.find("small")
    if small:
        set_text(small, "Department of Communication")


def fix_professional_menu(soup):
    labels = {
        "https://jmc.yonsei.ac.kr/jmc/index.do": "M.A. Programs",
        "https://jmc.yonsei.ac.kr/jmc/YSJ01.do": "YSJ Program",
        "https://jmc.yonsei.ac.kr/jmc/jmc01/high01.do": "Executive Program",
    }
    parent = None
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if href in labels:
            set_text(a, labels[href])
            parent = a.find_parent("li", class_="nav-item")
    if parent:
        set_text(parent.find("a", class_="nav-link"), "Professional Programs")


def fix_people_menu(soup):
    faculty = soup.find("a", href=lambda h: h and Path(urlsplit(h).path).name == "people.html")
    if not faculty:
        return
    menu = faculty.find_parent("ul", class_="dropdown-menu")
    if not menu:
        return

    for a in list(menu.find_all("a", href=True)):
        if Path(urlsplit(a["href"]).path).name in {"people_emeritus.html", "people_profpractice.html"}:
            li = a.find_parent("li")
            if li:
                li.decompose()

    faculty_li = faculty.find_parent("li")
    if not faculty_li:
        return

    emeritus_li = soup.new_tag("li")
    emeritus_a = soup.new_tag("a", href="people_emeritus.html")
    emeritus_a["class"] = ["dropdown-item"]
    emeritus_a.string = "Professor Emeriti"
    emeritus_li.append(emeritus_a)

    former_li = soup.new_tag("li")
    former_a = soup.new_tag("a", href="people_emeritus.html#section_2")
    former_a["class"] = ["dropdown-item"]
    former_a.string = "Former Faculty"
    former_li.append(former_a)

    faculty_li.insert_after(former_li)
    faculty_li.insert_after(emeritus_li)


def fix_language_toggle(soup, page_name):
    switcher = soup.select_one("#langSwitcher")
    if not switcher:
        return
    switcher.clear()

    href = "../" if page_name == "index.html" else f"../{page_name}"
    link = soup.new_tag("a", href=href)
    link["class"] = ["lang-direct-toggle"]
    link["aria-label"] = "한국어 페이지로 이동"

    label = soup.new_tag("span")
    label.string = "KO"
    link.append(label)

    caret = soup.new_tag("span")
    caret["class"] = ["lang-direct-toggle-caret"]
    caret["aria-hidden"] = "true"
    caret.string = "▾"
    link.append(caret)
    switcher.append(link)

    for widget in list(soup.select("#google_translate_element")):
        widget.decompose()


def fix_people(soup):
    add_body_class(soup, "page-people-en")
    for card in soup.select(".team-item"):
        img = card.find("img", src=True)
        if not img:
            continue
        key = Path(urlsplit(img["src"]).path).name
        data = PEOPLE.get(key)
        if not data:
            continue
        body = card.select_one(".px-4.py-3")
        if not body:
            continue

        set_text(body.find("h5"), data["name"] + " |")

        paragraphs = body.find_all("p", recursive=False)
        if paragraphs and "role" in data:
            set_text(paragraphs[0].find("small"), data["role"])

        for child in body.children:
            if getattr(child, "name", None) == "small":
                set_text(child, data["fields"])
                break


def fix_intro(soup):
    block = soup.select_one(".about-section .custom-text-block")
    if not block:
        return

    set_text(block.find("h2"), "Welcome")
    subtitle = block.find("p", class_=lambda c: c and "text-muted" in c.split())
    set_text(subtitle, "Department Head | Hyunjin Song")

    paragraphs = [p for p in block.find_all("p", recursive=False) if p is not subtitle]
    full_names = [
        "The Department of Communication at Yonsei University",
        "Yonsei University's Department of Communication",
        "Yonsei University’s Department of Communication",
        "Yonsei University Department of Communication",
        "Department of Communication at Yonsei University",
    ]

    # Contextual shorthand: institutional belief/future -> We; institutional
    # history/research record -> The Department.
    replacements = {
        1: "We",
        2: "The Department",
        3: "We",
    }
    for index, p in enumerate(paragraphs):
        value = p.get_text(" ", strip=True)
        replacement = replacements.get(index, "The Department")
        for phrase in full_names:
            value = value.replace(phrase, replacement)
        set_text(p, value)


def fix_curriculum(soup):
    add_body_class(soup, "page-curriculum-en")

    section = soup.select_one("#graduation-requirement")
    if not section:
        return

    heading_wrap = section.select_one(".col-12.text-center")
    if not heading_wrap:
        return

    set_text(heading_wrap.find("h2"), "Degree Requirements")
    subtitle = heading_wrap.find("h5")
    if subtitle:
        subtitle.decompose()


def fix_emeritus(soup):
    header = soup.select_one(".people-detail-header-section h3")
    set_text(header, "People")

    titles = soup.select(".section-title h3")
    if titles:
        set_text(titles[0], "Professor Emeriti")
    if len(titles) > 1:
        set_text(titles[1], "Former Faculty")

    for card in soup.select(".service-item"):
        img = card.find("img", src=True)
        if not img:
            continue
        key = Path(urlsplit(img["src"]).path).name
        name = EMERITUS.get(key)
        if not name:
            continue
        h5 = card.find("h5")
        if h5:
            bold = h5.find("b")
            set_text(bold or h5, name)


def process(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    if soup.html:
        soup.html["lang"] = "en"
    inject_stylesheets(soup)
    fix_brand(soup)
    fix_professional_menu(soup)
    fix_people_menu(soup)
    fix_language_toggle(soup, path.name)

    if path.name == "people.html":
        fix_people(soup)
    elif path.name == "intro.html":
        fix_intro(soup)
    elif path.name in {"curriculum.html", "curriculum_graduate.html"}:
        fix_curriculum(soup)
    elif path.name == "people_emeritus.html":
        fix_emeritus(soup)

    path.write_text(str(soup), encoding="utf-8")


def main():
    for path in sorted(ROOT.glob("*.html")):
        process(path)


if __name__ == "__main__":
    main()
