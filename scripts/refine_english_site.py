#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString

ROOT = Path("build/en")


def set_text(tag, text):
    if tag is None:
        return
    tag.clear()
    tag.append(text)


def set_badge_text(tag, text, aria=None):
    if tag is None:
        return
    icon = tag.find("i")
    strong = tag.find("strong")
    if strong:
        set_text(strong, text)
    else:
        tag.clear()
        if icon:
            tag.append(icon)
            tag.append(NavigableString("\u00a0" + text))
        else:
            tag.append(text)
    tag["aria-label"] = aria or text


def refine_navigation(soup):
    for a in soup.find_all("a", href=True):
        target = Path(urlsplit(a["href"]).path).name
        if target == "research_institute.html":
            set_text(a, "Research Centers")

    for a in list(soup.find_all("a", href=True)):
        if Path(urlsplit(a["href"]).path).name == "people_profpractice.html":
            li = a.find_parent("li")
            if li:
                li.decompose()


def refine_carousel(soup):
    captions = {
        "Communication": "Grounded in empathy, a future opened by creativity",
        "AI & Digital Media": "New possibilities through technology and data",
        "Strategy": "Moving the world through persuasion and messages",
        "Connection": "Inclusion that connects us beyond differences",
        "Accountability": "A responsible perspective committed to truth",
    }
    for item in soup.select("#hero-slide .carousel-item"):
        heading = item.find("h2")
        sub = item.find("h5")
        if heading and sub:
            label = heading.get_text(" ", strip=True)
            if label in captions:
                set_text(sub, captions[label])


def refine_academic_cards(soup):
    labels = {
        "curriculum.html": ("Undergraduate", "Academics"),
        "curriculum_graduate.html": ("Graduate Program", "Academics"),
    }
    for a in soup.select(".featured-block a[href]"):
        target = Path(urlsplit(a["href"]).path).name
        if target not in labels:
            continue
        p = a.find("p", class_="featured-block-text")
        if not p:
            continue
        first, second = labels[target]
        p.clear()
        p.append(first)
        p.append(soup.new_tag("br"))
        strong = soup.new_tag("strong")
        strong.string = second
        p.append(strong)


def refine_about_and_mission(soup):
    for box in soup.select(".custom-text-box"):
        h2 = box.find("h2")
        h5 = box.find("h5")

        if h2 and h2.get_text(" ", strip=True) == "About":
            set_text(h5, "Delivering truth, connecting the world |")
            h10 = box.find("h10")
            if h10:
                more = h10.find("a", class_="custom-btn")
                href = more.get("href", "intro.html#more_history") if more else "intro.html#more_history"
                h10.clear()
                h10.append(
                    "Since its founding in 1972 as the Department of Journalism and Broadcasting, "
                    "the Department has been at the forefront of journalism, communication, "
                    "advertising, and visual-media education in Korea, navigating half a century "
                    "of transformation in the media environment. The Department of Communication "
                    "at Yonsei University continues to connect people and society through democratic communication."
                )
                h10.append(soup.new_tag("p"))
                a = soup.new_tag("a", href=href)
                a["class"] = ["custom-btn", "btn"]
                a.string = "More"
                h10.append(a)

        if h5 and h5.get_text(" ", strip=True) == "Our Mission":
            set_text(
                box.find("h10"),
                "Educating professionals to address complex social problems in the age of AI-mediated communication",
            )
            bullets = [
                "Creative and innovative research clusters",
                "Leading, interdisciplinary education that cultivates global media intelligence",
            ]
            for li, text in zip(box.select("ul.custom-list li.custom-list-item"), bullets):
                icon = li.find("i")
                if icon:
                    icon.extract()
                li.clear()
                if icon:
                    li.append(icon)
                    li.append(NavigableString(" "))
                li.append(text)

    iframe = soup.find("iframe", title=True)
    if iframe and "50" in iframe.get("title", ""):
        iframe["title"] = "50th Anniversary Interviews: Department of Communication, Yonsei University"


def refine_facilities(soup):
    for info in soup.select(".news-block-info"):
        title = info.select_one(".news-block-title h4")
        if not title:
            continue
        current = title.get_text(" ", strip=True).lower()
        if "global" in current and ("media" in current or "studio" in current):
            new_title = "Global Media Studio"
            tags = ("#GlobalMediaStudio", "Baekyang Hall N208-1")
        elif "vr" in current or "virtual reality" in current:
            new_title = "Virtual Reality Lab"
            tags = ("#VRLab", "Billingsley Hall 208")
        else:
            continue

        set_text(title, new_title)
        body = info.select_one(".news-block-body")
        if body:
            body.decompose()

        card = info.find_parent("div", class_=lambda c: c and "news-block" in c.split())
        if card:
            links = card.select(".news-category-block .category-block-link")
            for link, value in zip(links, tags):
                set_text(link, value)


def refine_directions(soup):
    section = soup.select_one("#section_6")
    if not section:
        return

    set_text(section.find("h2"), "Directions")
    tables = section.select("table.subway-table")
    if not tables:
        return

    subway = tables[0]
    heads = subway.select("thead th")
    if len(heads) >= 2:
        set_text(heads[0], "Station")
        set_text(heads[1], "Exit Information")

    exits = [
        "Exit 2 (toward Yonsei University / Severance Hospital)",
        "Exit 3 (toward Yonsei University / Ewha Womans University)",
        "Exit 2 (toward Severance Hospital / Ewha Womans University)",
    ]
    for i, row in enumerate(subway.select("tbody tr")):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        set_text(cells[0].select_one(".station-name"), "Sinchon Station")
        badge = cells[0].select_one(".subway-badge")
        if badge:
            if "line-k3" in badge.get("class", []):
                set_badge_text(badge, "Gyeongui", "Gyeongui Line")
            else:
                set_badge_text(badge, "Line 2", "Seoul Subway Line 2")
        if len(cells) > 1 and i < len(exits):
            set_text(cells[1], exits[i])

    if len(tables) < 2:
        return

    bus = tables[1]
    heads = bus.select("thead th")
    if len(heads) >= 2:
        set_text(heads[0], "Bus Stop")
        set_text(heads[1], "Routes")

    stops = [
        "Yonsei University / Yonsei Univ. Front",
        "Yonsei University Main Gate",
        "Severance Hospital (Median Bus Lane)",
        "Severance Hospital",
    ]
    for i, row in enumerate(bus.select("tbody tr")):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        if i < len(stops):
            set_text(cells[0], stops[i])

        red_seen = 0
        for badge in cells[1].select(".subway-badge"):
            classes = badge.get("class", [])
            if "line-1" in classes:
                set_badge_text(badge, "B", "B bus")
            elif "line-2" in classes:
                set_badge_text(badge, "G", "G bus")
            elif "line-airportbus" in classes:
                set_badge_text(badge, "Airport", "Airport bus")
            elif "line-redbus" in classes:
                red_seen += 1
                if red_seen == 1:
                    set_badge_text(badge, "R", "R bus")
                else:
                    set_badge_text(badge, "Express", "Express bus")


def refine_index(soup):
    refine_carousel(soup)
    refine_academic_cards(soup)
    refine_about_and_mission(soup)
    refine_facilities(soup)
    refine_directions(soup)


def process(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    refine_navigation(soup)
    if path.name == "index.html":
        refine_index(soup)
    path.write_text(str(soup), encoding="utf-8")


def main():
    for path in sorted(ROOT.glob("*.html")):
        process(path)


if __name__ == "__main__":
    main()
