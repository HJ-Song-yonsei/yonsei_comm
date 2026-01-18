#!/usr/bin/env python3
import json, re, sys, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

# --- 기본 설정 ---
DEPT_SLUG = "department-of-communication"
BASE_URL = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/publications/"
QS = "ordering=publicationYearThenTitle&descending=true&format=rss"
RSS_URL = f"{BASE_URL}?{QS}"
OUT_PATH = "data/pure_publications_2000plus.json"
MIN_YEAR = 2010
MAX_ITEMS = 1000

# --- Network Map 설정 ---
MAP_URL = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/network-map-json/"
# 교수님이 확인하신 URL 패턴 (물음표 앞 슬래시 포함)을 반영
COUNTRY_MAP_BASE = f"https://yonsei.elsevierpure.com/en/organisations/{DEPT_SLUG}/network-map-json-country"
MAP_OUT_PATH = "data/network_map.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- 유틸리티 함수 ---
def http_get(url: str) -> bytes:
    """X-Requested-With 헤더를 포함하여 API 보안 요구사항을 충족합니다."""
    headers = {
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as r:
        return r.read()

def rss_url(page: int) -> str:
    return f"{BASE_URL}?{QS}&page={page}"

def parse_rss_items(rss_xml: str):
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    root = ET.fromstring(rss_xml)
    channel = root.find("channel")
    if channel is None: return []

    out = []
    for item in channel.findall("item"):
        it_title = (item.findtext("title") or "").strip()
        it_link  = (item.findtext("link") or "").strip() or (item.findtext("guid") or "").strip()
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
        if vals: return vals[0].strip()
    return ""

def normalize_outlet(html: str): return first_meta(html, ["citation_journal_title", "citation_conference_title", "citation_book_title", "citation_publisher"])
def normalize_type(html: str): return first_meta(html, ["citation_article_type"])
def normalize_doi(html: str): return first_meta(html, ["citation_doi"])
def normalize_authors(html: str): return [a.strip() for a in find_meta(html, "citation_author") if a.strip()]
def year_from_iso(iso: str):
    m = re.match(r"^(\d{4})-", iso or "")
    return int(m.group(1)) if m else None

# --- 협력 기관 상세 수집 함수 ---
def get_institution_list(country_id, subdivision_id=None):
    """
    제공해주신 데이터 형식을 파싱하여 대학교 명단을 추출합니다.
    """
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
            # <span> 태그 내 기관명 추출
            match = re.search(r"<span>(.*?)</span>", html_content)
            if match:
                institutions.add(match.group(1).strip())
        
        return sorted(list(institutions))
    except Exception:
        return []

# --- 메인 실행 로직 ---
def main():
    # 1. Publication 수집 (기존 코드 유지)
    print("Step 1: Fetching publications...")
    try:
        rss_xml = http_get(RSS_URL).decode("utf-8", errors="replace")
        root = ET.fromstring(rss_xml)
        channel = root.find("channel")
        title = (channel.findtext("title") or "").strip()
        link = (channel.findtext("link") or "").strip()
        desc = (channel.findtext("description") or "").strip()
        last_build = (channel.findtext("lastBuildDate") or "").strip()
    except Exception as e:
        print(f"Error: {e}")
        return

    items = []
    seen = set()
    page = 0
    
    while True:
        print(f"  - RSS Page {page}...")
        try:
            current_rss = http_get(rss_url(page)).decode("utf-8", errors="replace")
            page_rows = parse_rss_items(current_rss)
        except: break

        new_rows = [r for r in page_rows if r[1] not in seen]
        if not new_rows: break

        for (it_title, it_link, dc_date, y) in new_rows:
            seen.add(it_link)
            if y < MIN_YEAR: continue
            try:
                html = http_get(it_link).decode("utf-8", errors="replace")
                items.append({
                    "title": it_title, "link": it_link, "dc:date": dc_date, "year": y,
                    "authors": normalize_authors(html), "outlet": normalize_outlet(html),
                    "doi": normalize_doi(html), "type": normalize_type(html),
                })
                time.sleep(0.1)
            except: continue

        if min(r[3] for r in new_rows) < MIN_YEAR: break
        page += 1
        if page > 50: break

    # 논문 데이터 저장
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items, "generatedAt": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)

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
                print(f"  - Skipping details for home country (Korea)")
                item["institutions"] = []
                continue
                
            print(f"  - Fetching details for {c_id} {s_id or ''}...")
            item["institutions"] = get_institution_list(c_id, s_id)
            time.sleep(0.5) # 서버 차단 방지용 딜레이
            
        with open(MAP_OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved enriched map to {MAP_OUT_PATH}")
        
    except Exception as e:
        print(f"Map Error: {e}")

if __name__ == "__main__":
    main()