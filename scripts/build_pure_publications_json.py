#!/usr/bin/env python3
import json, os, re, time
import ssl
import certifi
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

# --- 기본 설정 ---
DEPT_SLUG = "department-of-communication"
BASE_URL = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/publications/"
MIN_YEAR = 2010
MAX_ITEMS = 1000
QS = f"ordering=publicationYearThenTitle&descending=true&format=rss&pageSize={MAX_ITEMS}"
RSS_URL = f"{BASE_URL}?{QS}"
OUT_PATH = "data/pure_publications_2000plus.json"

# --- Network Map 설정 ---
MAP_URL = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/network-map-json/"
# URL 패턴 (물음표 앞 슬래시 포함)을 반영
COUNTRY_MAP_BASE = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/network-map-json-country"
MAP_OUT_PATH = "data/network_map.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- 유틸리티 함수 ---
def http_get(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    """Fetch a URL with retry/backoff while preserving the existing Pure headers."""
    headers = {
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }

    # 로컬 Python의 인증서 문제를 피하기 위해 certifi 인증서 묶음을 명시적으로 사용
    context = ssl.create_default_context(cafile=certifi.where())
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout, context=context) as r:
                return r.read()
        except Exception as e:
            last_error = e
            print(f"HTTP attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(attempt * 5)

    raise last_error


def parse_rss_items(rss_xml: str):
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    root = ET.fromstring(rss_xml)
    channel = root.find("channel")
    if channel is None:
        return []

    out = []
    for item in channel.findall("item"):
        it_title = (item.findtext("title") or "").strip()
        it_link = (item.findtext("link") or "").strip() or (item.findtext("guid") or "").strip()
        dc_date_el = item.find("dc:date", ns)
        dc_date = (dc_date_el.text.strip() if (dc_date_el is not None and dc_date_el.text) else "").strip()
        y = year_from_iso(dc_date)
        if it_title and it_link and y:
            out.append((it_title, it_link, dc_date, y))
    return out


# --- 메타데이터 추출 함수 ---
def find_meta(html: str, name: str):
    pat = re.compile(r'<meta\s+(?:name|property)\s*=\s*["\']%s["\']\s+content\s*=\s*["\']([^"\']+)["\']\s*/?>' % re.escape(name), re.I)
    return pat.findall(html)


def first_meta(html: str, candidates):
    for c in candidates:
        vals = find_meta(html, c)
        if vals:
            return vals[0].strip()
    return ""


def normalize_outlet(html: str):
    return first_meta(html, ["citation_journal_title", "citation_conference_title", "citation_book_title", "citation_publisher"])


def normalize_type(html: str):
    return first_meta(html, ["citation_article_type"])


def normalize_doi(html: str):
    return first_meta(html, ["citation_doi"])


def normalize_authors(html: str):
    return [a.strip() for a in find_meta(html, "citation_author") if a.strip()]


def year_from_iso(iso: str):
    m = re.match(r"^(\d{4})-", iso or "")
    return int(m.group(1)) if m else None


# --- 협력 기관 상세 수집 함수 ---
def get_institution_list(country_id, subdivision_id=None):
    """협력 기관 상세 API를 파싱하여 대학교 명단을 추출합니다."""
    c_id = country_id.lower()

    if subdivision_id:
        # 미국 등 subdivision이 있는 경우 (?country=us&subdivision=ga)
        s_id = subdivision_id.lower()
        full_url = f"{COUNTRY_MAP_BASE}/?country={c_id}&subdivision={s_id}"
    else:
        # 일반 국가인 경우 (/?country=at)
        full_url = f"{COUNTRY_MAP_BASE}/?country={c_id}"

    try:
        raw = http_get(full_url).decode("utf-8", errors="replace")
        data = json.loads(raw)

        institutions = set()
        for org in data.get("organisations", []):
            html_content = org.get("rendering", "")
            match = re.search(r"<span>(.*?)</span>", html_content)
            if match:
                institutions.add(match.group(1).strip())

        return sorted(list(institutions))
    except Exception:
        return []


# --- 메인 실행 로직 ---
def main():
    # 기존 저장본을 publication-detail cache로 사용합니다.
    existing_items = []
    existing_by_link = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                existing_items = json.load(f).get("items", [])
            existing_by_link = {
                item.get("link"): item
                for item in existing_items
                if item.get("link")
            }
            print(f"Loaded {len(existing_items)} cached publication records.")
        except Exception as e:
            print(f"Warning: could not read existing Pure JSON for cache/sanity check: {e}")
            existing_items = []
            existing_by_link = {}

    # 1. Publication 수집
    print("Step 1: Fetching publications...")
    try:
        rss_xml = http_get(RSS_URL).decode("utf-8", errors="replace")
        root = ET.fromstring(rss_xml)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS channel not found")
        page_rows = parse_rss_items(rss_xml)
    except Exception as e:
        print(f"ERROR: Failed to fetch Pure publication feed after retries: {e}")
        raise SystemExit(1)

    if not page_rows:
        print("ERROR: Pure RSS returned no publication items; keeping the existing JSON unchanged.")
        raise SystemExit(1)

    print(f"  - RSS returned {len(page_rows)} publication records in one request.")

    # pageSize 한도에 정확히 닿으면 결과가 잘렸을 가능성이 있으므로 저장하지 않습니다.
    if len(page_rows) >= MAX_ITEMS:
        print(
            f"ERROR: Pure RSS returned {len(page_rows)} items, reaching pageSize={MAX_ITEMS}. "
            "The feed may be truncated; keeping the existing JSON unchanged."
        )
        raise SystemExit(1)

    # RSS를 authoritative list로 사용하되 중복 link는 제거합니다.
    filtered_rows = []
    seen = set()
    for row in page_rows:
        it_title, it_link, dc_date, y = row
        if it_link in seen or y < MIN_YEAR:
            continue
        seen.add(it_link)
        filtered_rows.append(row)

    # 서버 측 차단/축약 때문에 대량 삭제가 생기는 것을 상세 fetch 전에 방지합니다.
    existing_count = len(existing_items)
    if existing_count and len(filtered_rows) < existing_count * 0.75:
        print(
            f"ERROR: Current Pure RSS has only {len(filtered_rows)} items from {MIN_YEAR} onward "
            f"versus {existing_count} cached items. Refusing to overwrite because the feed may be incomplete."
        )
        raise SystemExit(1)

    items = []
    reused_count = 0
    fetched_count = 0

    for (it_title, it_link, dc_date, y) in filtered_rows:
        cached = existing_by_link.get(it_link)

        if cached is not None:
            # RSS의 현재 title/date/year는 반영하되, 비용이 큰 상세 metadata는 cache를 재사용합니다.
            item = dict(cached)
            item.update({
                "title": it_title,
                "link": it_link,
                "dc:date": dc_date,
                "year": y,
            })
            items.append(item)
            reused_count += 1
            continue

        # 처음 보는 publication만 상세 페이지를 조회합니다.
        print(f"  - Fetching new publication detail: {it_title}")
        try:
            html = http_get(it_link).decode("utf-8", errors="replace")
        except Exception as e:
            print(
                f"ERROR: Failed to fetch detail for new publication after retries: {it_link}: {e}. "
                "Keeping the existing JSON unchanged."
            )
            raise SystemExit(1)

        items.append({
            "title": it_title,
            "link": it_link,
            "dc:date": dc_date,
            "year": y,
            "authors": normalize_authors(html),
            "outlet": normalize_outlet(html),
            "doi": normalize_doi(html),
            "type": normalize_type(html),
        })
        fetched_count += 1
        time.sleep(0.1)

    print(
        f"  - Prepared {len(items)} publications from {MIN_YEAR} onward "
        f"({reused_count} cached, {fetched_count} newly fetched)."
    )

    # 논문 목록/metadata에 실질적 변화가 없으면 generatedAt만 바꾸는 불필요한 commit을 만들지 않습니다.
    if items == existing_items:
        print(f"No substantive change: {OUT_PATH}")
    else:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"items": items, "generatedAt": datetime.now(timezone.utc).isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Updated: {OUT_PATH}")

    # 2. Network Map 데이터 통합 (한국 제외)
    print("Step 2: Enriching Network Map Data...")
    try:
        map_raw = http_get(MAP_URL).decode("utf-8", errors="replace")
        map_data = json.loads(map_raw)

        for item in map_data.get("countries", []):
            c_id = item.get("countryId")
            s_id = item.get("subdivisionId")
            is_home = item.get("homeCountry", False)

            # 한국(Home Country)인 경우 상세 수집 건너뛰기
            if is_home or (c_id and c_id.lower() == "kr"):
                print("  - Skipping details for home country (Korea)")
                item["institutions"] = []
                continue

            print(f"  - Fetching details for {c_id} {s_id or ''}...")
            item["institutions"] = get_institution_list(c_id, s_id)
            time.sleep(0.5)  # 서버 차단 방지용 딜레이

        with open(MAP_OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved enriched map to {MAP_OUT_PATH}")

    except Exception as e:
        print(f"Map Error: {e}")


if __name__ == "__main__":
    main()
