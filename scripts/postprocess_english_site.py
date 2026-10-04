#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, NavigableString

ROOT = Path("build/en")

PEOPLE = {
    "taewookang.jpg": {"name": "Taewoo Kang", "fields": "Digital Platforms | AI | Political Communication"},
    "kkmo.jpg": {"name": "Kyoungmo Kim", "role": "JMC YSJ Program Chair", "fields": "Journalism | Content Analysis | International Communication"},
    "yckim.jpg": {"name": "Yong-Chan Kim", "role": "Vice President for International Affairs", "fields": "AI & Platform Media | Digital Cities | Risk Society & Polarization"},
    "jrkim.jpg": {"name": "Jarim Kim", "fields": "Risk & Crisis Communication | Public Relations | Persuasion"},
    "jkim.jpg": {"name": "Joohan Kim", "fields": "Neuroscience | Inner Communication | Communication Competence"},
    "Namkee_Park.jpg": {"name": "Namkee Park", "role": "Dean, Graduate School of Journalism & Mass Communication", "fields": "New Media Technology | Human-AI Interaction"},
    "ymbaek.jpg": {"name": "Young Min Baek", "fields": "Political Communication | Social Science Research Methods"},
    "jpaek.jpg": {"name": "Jihyun Paik", "fields": "Interpersonal Communication | Organizational Communication"},
    "ymsang.jpg": {"name": "Yoonmo Sang", "role": "JMC Journalism Program Chair", "fields": "Media Law | Journalism Ethics | Copyright"},
    "yhsung.jpg": {"name": "Yoonhee Sung", "role": "Associate Dean, Graduate School of Journalism & Mass Communication; JMC PR/Advertising Program Chair", "fields": "Advertising & Media Technology | Consumer Analysis"},
    "jso.jpg": {"name": "Jiyeon So", "role": "Graduate Program Chair", "fields": "Health Communication | Persuasion | Science Communication"},
    "hyunjinsong.jpg": {"name": "Hyunjin Song", "role": "Department Head", "fields": "Political Communication | Computational Social Science | Processing Fluency"},
    "larosa.jpg": {"name": "Nayeon Lee", "fields": "Journalism Principles | Online Journalism | News Audiences"},
    "sylee.jpg": {"name": "Sang Yup Lee", "fields": "Computational Social Science | Data Science | Artificial Intelligence"},
    "ccho.jpg": {"name": "Chang-Hoan Cho", "fields": "Digital Advertising | Advertising Campaigns | Branded Communication"},
    "sychoi3.jpg": {"name": "Seokyoung Choi", "role": "JMC Broadcasting/Visual Media/Cultural Content Program Chair", "fields": "Communication Technology | AI | Games"},
}


def set_text(tag, text):
    if tag is None:
        return
    tag.clear()
    tag.append(text)


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
        top = parent.find("a", class_="nav-link")
        set_text(top, "Professional Programs")


def fix_people(soup):
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
        h5 = body.find("h5")
        set_text(h5, data["name"] + " |")
        paragraphs = body.find_all("p", recursive=False)
        if paragraphs and "role" in data:
            small = paragraphs[0].find("small")
            set_text(small, data["role"])
        for child in body.children:
            if getattr(child, "name", None) == "small":
                set_text(child, data["fields"])
                break


def inject_css(soup):
    if not soup.head:
        return
    if soup.find("link", href="../css/en.css"):
        return
    link = soup.new_tag("link", rel="stylesheet", href="../css/en.css")
    soup.head.append(link)


def process(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    fix_brand(soup)
    fix_professional_menu(soup)
    inject_css(soup)
    if path.name == "people.html":
        fix_people(soup)
    path.write_text(str(soup), encoding="utf-8")


def main():
    for path in sorted(ROOT.glob("*.html")):
        process(path)


if __name__ == "__main__":
    main()
