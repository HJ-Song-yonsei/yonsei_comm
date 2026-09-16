#!/usr/bin/env python3
"""Build a JSON feed of domestic journal articles from Yonsei FIS.

Designed for scheduled execution in GitHub Actions.
The generated feeds can be consumed immediately by the research-area JSON builders.

Outputs
-------
- data/fis_domestic_publications.json
- data/fis_publications_review.json

Classification policy
---------------------
1) Explicit domestic_journal_overrides => domestic
2) Explicit foreign_journal_overrides  => foreign
3) Journal title containing Hangul      => domestic
4) Everything else                     => review (not silently discarded)

This intentionally uses a conservative rule for English-titled journals.
Add known Korean journals with English titles to the YAML override list.
"""

from __future__ import annotations

import copy
import html as html_lib
import json
import os
import re
import ssl
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

import certifi
import yaml
from bs4 import BeautifulSoup

CONFIG_PATH = Path(os.environ.get("FIS_CONFIG_PATH", "config/fis_publications.yml"))
FIS_BASE = "https://fis.yonsei.ac.kr"
REPORT_ENDPOINT = f"{FIS_BASE}/faculty/depMember.do"
SEARCH_ENDPOINT = f"{FIS_BASE}/faculty/member.do"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HANGUL_RE = re.compile(r"[가-힣]")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
SPACE_RE = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(value: str | None) -> str:
    if not value:
        return ""
    return SPACE_RE.sub(" ", html_lib.unescape(value)).strip()


def norm_journal(value: str | None) -> str:
    # Casefold makes override matching case-insensitive while retaining Unicode.
    return norm_text(value).casefold()


def http_get(url: str, retries: int = 3, delay: float = 1.5) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{FIS_BASE}/faculty/depMember.do",
        "Cache-Control": "no-cache",
    }
    req = Request(url, headers=headers)
    context = ssl.create_default_context(cafile=certifi.where())

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=30, context=context) as response:
                return response.read()
        except Exception as exc:  # network failures should be retried
            last_error = exc
            if attempt < retries:
                time.sleep(delay * attempt)
    assert last_error is not None
    raise last_error


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("faculty"):
        raise ValueError(f"No faculty entries found in {path}")
    return cfg


def encoded_user_id(user_id: str) -> str:
    """Normalize either encoded or decoded FIS userId into URL-safe form."""
    return quote(unquote(user_id.strip()), safe="")


def report_url(user_id: str) -> str:
    uid = encoded_user_id(user_id)
    return f"{REPORT_ENDPOINT}?mode=report&reportType=article&userId={uid}"


def profile_url(user_id: str) -> str:
    uid = encoded_user_id(user_id)
    return f"{REPORT_ENDPOINT}?mode=view&userId={uid}"


def user_id_from_href(href: str) -> str | None:
    try:
        parsed = urlparse(urljoin(FIS_BASE, href))
        value = parse_qs(parsed.query).get("userId", [None])[0]
        return value.strip() if value else None
    except Exception:
        return None


def discover_user_id(name: str) -> str | None:
    """Try to discover a missing FIS userId from the public name-search page."""
    url = f"{SEARCH_ENDPOINT}?srSearchVal={quote(name, safe='')}"
    raw = http_get(url).decode("utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    anchors = [a for a in soup.find_all("a", href=True) if "userId=" in a.get("href", "")]

    # Prefer a link whose nearby faculty card contains the exact Korean name.
    for a in anchors:
        node = a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            text = norm_text(node.get_text(" ", strip=True))
            if name in text:
                uid = user_id_from_href(a["href"])
                if uid:
                    return uid

    # Exact-name searches often return a single profile. Use only if unambiguous.
    ids = []
    for a in anchors:
        uid = user_id_from_href(a["href"])
        if uid and uid not in ids:
            ids.append(uid)
    return ids[0] if len(ids) == 1 else None


def normalize_header(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", norm_text(text).casefold())


def header_role(header: str) -> str | None:
    h = normalize_header(header)
    if h in {"issuedate", "issue", "date", "발행일", "발행년월", "게재일", "출판일"}:
        return "issueDate"
    if h in {"title", "논문명", "논문제목", "제목"}:
        return "title"
    if h in {"journals", "journal", "학술지", "학술지명", "저널"}:
        return "journal"
    return None


def table_rows(table) -> list[dict[str, str]]:
    rows = table.find_all("tr")
    if not rows:
        return []

    # Locate a header row that identifies at least title + journal.
    header_index = None
    roles: list[str | None] = []
    for i, tr in enumerate(rows[:5]):
        cells = tr.find_all(["th", "td"])
        candidate = [header_role(c.get_text(" ", strip=True)) for c in cells]
        if "title" in candidate and "journal" in candidate:
            header_index = i
            roles = candidate
            break

    out: list[dict[str, str]] = []
    if header_index is not None:
        for tr in rows[header_index + 1 :]:
            cells = tr.find_all("td")
            if not cells:
                continue
            item = {"issueDate": "", "title": "", "journal": "", "publicationUrl": ""}
            for idx, cell in enumerate(cells):
                if idx >= len(roles) or not roles[idx]:
                    continue
                role = roles[idx]
                item[role] = norm_text(cell.get_text(" ", strip=True))
                if role == "title":
                    a = cell.find("a", href=True)
                    if a:
                        item["publicationUrl"] = urljoin(FIS_BASE, a["href"])
            if item["title"] and item["journal"]:
                out.append(item)
        return out

    # Fallback for a simple three-column table: date | title | journal.
    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        texts = [norm_text(c.get_text(" ", strip=True)) for c in cells]
        if not YEAR_RE.search(texts[0]):
            continue
        item = {
            "issueDate": texts[0],
            "title": texts[1],
            "journal": texts[2],
            "publicationUrl": "",
        }
        a = cells[1].find("a", href=True)
        if a:
            item["publicationUrl"] = urljoin(FIS_BASE, a["href"])
        if item["title"] and item["journal"]:
            out.append(item)
    return out


def parse_report_html(raw_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(raw_html, "html.parser")
    candidates: list[list[dict[str, str]]] = []
    for table in soup.find_all("table"):
        rows = table_rows(table)
        if rows:
            candidates.append(rows)

    if candidates:
        # The publication table should be the one with the most valid rows.
        return max(candidates, key=len)

    # Last-resort fallback: inspect repeated row-like structures containing a year.
    rows: list[dict[str, str]] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        texts = [norm_text(c.get_text(" ", strip=True)) for c in cells]
        if len(texts) >= 3 and YEAR_RE.search(texts[0]):
            rows.append({
                "issueDate": texts[0],
                "title": texts[1],
                "journal": texts[2],
                "publicationUrl": "",
            })
    return rows


def extract_year(issue_date: str) -> int | None:
    m = YEAR_RE.search(issue_date or "")
    return int(m.group(0)) if m else None


def classify_journal(
    journal: str,
    domestic_overrides: set[str],
    foreign_overrides: set[str],
) -> tuple[str, str]:
    key = norm_journal(journal)
    if key in domestic_overrides:
        return "domestic", "domestic_override"
    if key in foreign_overrides:
        return "foreign", "foreign_override"
    if HANGUL_RE.search(journal or ""):
        return "domestic", "hangul_journal_title"
    return "review", "english_or_nonhangul_unclassified"


def date_sort_key(issue_date: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d+", issue_date or "")]
    year = nums[0] if nums and 1900 <= nums[0] <= 2100 else (extract_year(issue_date) or 0)
    month = nums[1] if len(nums) > 1 and 1 <= nums[1] <= 12 else 0
    day = nums[2] if len(nums) > 2 and 1 <= nums[2] <= 31 else 0
    return year, month, day


def payload_without_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(payload)
    cloned.pop("generatedAt", None)
    return cloned


def write_json_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    """Avoid changing generatedAt (and Git history) when substantive data is unchanged."""
    old: dict[str, Any] | None = None
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            old = None

    if old is not None and payload_without_generated_at(old) == payload_without_generated_at(payload):
        print(f"No substantive change: {path}")
        return False

    payload["generatedAt"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"Updated: {path}")
    return True


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out = []
    for item in items:
        key = (
            item.get("faculty", ""),
            item.get("issueDate", ""),
            item.get("title", ""),
            item.get("journal", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main() -> int:
    cfg = load_config(CONFIG_PATH)

    min_year = int(cfg.get("min_year", 2010))
    request_delay = float(cfg.get("request_delay_seconds", 0.5))
    fail_on_required_error = bool(cfg.get("fail_on_required_error", True))

    domestic_overrides = {norm_journal(x) for x in cfg.get("domestic_journal_overrides", [])}
    foreign_overrides = {norm_journal(x) for x in cfg.get("foreign_journal_overrides", [])}

    output_path = Path(cfg.get("output_path", "data/fis_domestic_publications.json"))
    review_path = Path(cfg.get("review_output_path", "data/fis_publications_review.json"))

    domestic_items: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    faculty_stats: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    print("Step 1: Fetching FIS journal articles...")

    for idx, person in enumerate(cfg["faculty"], start=1):
        name = norm_text(person.get("name"))
        if not name:
            continue

        required = bool(person.get("required", True))
        uid = norm_text(person.get("user_id"))

        if not uid and person.get("auto_discover", True):
            print(f"  [{idx}/{len(cfg['faculty'])}] {name}: discovering userId...")
            try:
                uid = discover_user_id(name) or ""
            except Exception as exc:
                print(f"    discovery failed: {exc}")

        if not uid:
            msg = "FIS userId not found"
            print(f"  [{idx}/{len(cfg['faculty'])}] {name}: {msg}")
            errors.append({"faculty": name, "error": msg, "required": str(required).lower()})
            faculty_stats.append({"name": name, "status": "missing_user_id", "domesticCount": 0, "reviewCount": 0})
            continue

        url = report_url(uid)
        print(f"  [{idx}/{len(cfg['faculty'])}] {name}: fetching articles...")
        try:
            raw = http_get(url).decode("utf-8", errors="replace")
            rows = parse_report_html(raw)
            if not rows:
                raise ValueError("No publication rows parsed from FIS report page")
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"    ERROR: {msg}")
            errors.append({"faculty": name, "error": msg, "required": str(required).lower()})
            faculty_stats.append({"name": name, "status": "fetch_error", "domesticCount": 0, "reviewCount": 0})
            continue

        person_domestic = 0
        person_review = 0

        for row in rows:
            year = extract_year(row.get("issueDate", ""))
            if not year or year < min_year:
                continue

            classification, reason = classify_journal(
                row.get("journal", ""), domestic_overrides, foreign_overrides
            )

            item = {
                "faculty": name,
                "issueDate": row.get("issueDate", ""),
                "year": year,
                "title": row.get("title", ""),
                "journal": row.get("journal", ""),
                "publicationUrl": row.get("publicationUrl", ""),
                "fisProfileUrl": profile_url(uid),
                "classification": classification,
                "classificationReason": reason,
            }

            if classification == "domestic":
                domestic_items.append(item)
                person_domestic += 1
            elif classification == "review":
                review_items.append(item)
                person_review += 1

        faculty_stats.append({
            "name": name,
            "status": "ok",
            "domesticCount": person_domestic,
            "reviewCount": person_review,
        })
        print(f"    domestic={person_domestic}, review={person_review}, raw={len(rows)}")
        time.sleep(request_delay)

    # Do not publish a silently partial dataset if a required faculty scrape failed.
    required_errors = [e for e in errors if e.get("required") == "true"]
    if required_errors and fail_on_required_error:
        print("\nRequired faculty scrape(s) failed; existing JSON files will be preserved.", file=sys.stderr)
        for e in required_errors:
            print(f"  - {e['faculty']}: {e['error']}", file=sys.stderr)
        return 2

    domestic_items = dedupe(domestic_items)
    review_items = dedupe(review_items)

    domestic_items.sort(
        key=lambda x: (date_sort_key(x.get("issueDate", "")), x.get("faculty", ""), x.get("title", "")),
        reverse=True,
    )
    review_items.sort(
        key=lambda x: (date_sort_key(x.get("issueDate", "")), x.get("faculty", ""), x.get("title", "")),
        reverse=True,
    )

    faculty_stats.sort(key=lambda x: x["name"])
    journal_counts = Counter(item["journal"] for item in domestic_items)

    domestic_payload: dict[str, Any] = {
        "source": "Yonsei Faculty Information System (FIS)",
        "minYear": min_year,
        "itemCount": len(domestic_items),
        "facultyCount": sum(1 for x in faculty_stats if x.get("status") == "ok"),
        "faculty": faculty_stats,
        "journals": [
            {"journal": journal, "count": count}
            for journal, count in sorted(journal_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "items": domestic_items,
    }

    review_payload: dict[str, Any] = {
        "source": "Yonsei Faculty Information System (FIS)",
        "note": (
            "English/non-Hangul journal titles that are not in either override list. "
            "If a journal is a Korean domestic journal, add it to domestic_journal_overrides in config/fis_publications.yml."
        ),
        "minYear": min_year,
        "itemCount": len(review_items),
        "errors": errors,
        "items": review_items,
    }

    print("\nStep 2: Writing JSON feeds...")
    write_json_if_changed(output_path, domestic_payload)
    write_json_if_changed(review_path, review_payload)

    print(f"Done: {len(domestic_items)} domestic articles; {len(review_items)} review items.")
    if errors:
        print(f"Warnings: {len(errors)} faculty issue(s). See {review_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
