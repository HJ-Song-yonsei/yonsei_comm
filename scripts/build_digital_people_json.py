#!/usr/bin/env python3
"""Build a research-area people/output feed using FIS as publication source of truth.

Publication membership comes only from data/fis_publications_all.json. Yonsei Pure
is optional enrichment: for an exact normalized title match by the same faculty
member (and a compatible year), a DOI URL from Pure replaces/augments the FIS URL.
Pure never adds a publication that is absent from FIS.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("config/digital_people.yml")
PAGE_TITLE = "People in Digital Technology, Platform, & AI"
DEFAULT_OUTPUT_PATH = "data/digital_people.json"
SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^0-9a-z가-힣]+", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def norm_title(value: Any) -> str:
    text = norm_text(value).casefold()
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    return PUNCT_RE.sub("", text)


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        print(f"Warning: optional source not found: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def year_from_item(item: dict[str, Any]) -> int:
    try:
        return int(item.get("year") or 0)
    except Exception:
        m = re.search(r"(?:19|20)\d{2}", norm_text(item.get("dc:date") or item.get("issueDate")))
        return int(m.group(0)) if m else 0


def doi_url(doi: str) -> str:
    doi = norm_text(doi)
    return f"https://doi.org/{doi}" if doi else ""


def pure_doi_index(
    pure: dict[str, Any], aliases: set[str], min_year: int
) -> dict[str, dict[str, Any]]:
    """Return exact normalized-title -> DOI metadata for one faculty member."""
    alias_fold = {a.casefold() for a in aliases if a}
    out: dict[str, dict[str, Any]] = {}
    for item in pure.get("items", []):
        year = year_from_item(item)
        if year and year < min_year - 1:
            continue
        authors = [norm_text(a) for a in item.get("authors", [])]
        if not any(a.casefold() in alias_fold for a in authors):
            continue
        doi = norm_text(item.get("doi"))
        title = norm_text(item.get("title"))
        key = norm_title(title)
        if not key or not doi:
            continue
        candidate = {"year": year, "url": doi_url(doi), "title": title}
        # Prefer a record with a known year; otherwise first exact-title DOI wins.
        if key not in out or (not out[key].get("year") and year):
            out[key] = candidate
    return out


def publication_type(classification: str) -> str:
    value = norm_text(classification).casefold()
    if value == "domestic":
        return "domestic"
    if value == "foreign":
        return "international"
    return "review"


def fis_candidates(
    fis: dict[str, Any], faculty_name: str, min_year: int, doi_index: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Use every eligible FIS article; Pure can only enrich its URL with a DOI."""
    out: list[dict[str, Any]] = []
    for item in fis.get("items", []):
        if norm_text(item.get("faculty")) != faculty_name:
            continue
        year = year_from_item(item)
        if year < min_year:
            continue

        title = norm_text(item.get("title"))
        key = norm_title(title)
        fis_url = norm_text(item.get("publicationUrl"))
        url = fis_url
        url_source = "FIS" if fis_url else ""

        doi_match = doi_index.get(key)
        if doi_match:
            pure_year = int(doi_match.get("year") or 0)
            # Online-first / issue assignment can shift by one calendar year.
            if not pure_year or not year or abs(pure_year - year) <= 1:
                url = norm_text(doi_match.get("url")) or url
                if doi_match.get("url"):
                    url_source = "Pure DOI"

        out.append({
            "year": year,
            "title": title,
            "outlet": norm_text(item.get("journal")),
            "url": url,
            "urlSource": url_source,
            "source": "FIS",
            "publicationType": publication_type(item.get("classification", "")),
            "classificationReason": norm_text(item.get("classificationReason")),
        })

    # The full FIS feed may contain repeated rows differing only in issue metadata.
    # Deduplicate at display level by normalized title within a faculty member.
    merged: dict[str, dict[str, Any]] = {}
    for item in out:
        key = norm_title(item.get("title"))
        if not key:
            continue
        old = merged.get(key)
        if old is None:
            merged[key] = item
            continue
        if int(item.get("year") or 0) > int(old.get("year") or 0):
            merged[key] = item
            old = item
        if not old.get("url") and item.get("url"):
            old["url"] = item["url"]
            old["urlSource"] = item.get("urlSource", "")
    return list(merged.values())


def keyword_matches(haystack: str, keyword: str) -> bool:
    kw = norm_text(keyword).casefold()
    if not kw:
        return False
    if re.search(r"[가-힣]", kw):
        return kw in haystack
    stem = kw.endswith("*")
    if stem:
        kw = kw[:-1]
    escaped = re.escape(kw).replace(r"\ ", r"\s+")
    suffix = r"[a-z0-9_-]*" if stem else ""
    pattern = rf"(?<![a-z0-9]){escaped}{suffix}(?![a-z0-9])"
    return re.search(pattern, haystack, flags=re.I) is not None


def keyword_topics(item: dict[str, Any], topics_cfg: dict[str, Any]) -> tuple[list[str], int]:
    haystack = f"{norm_text(item.get('title'))} {norm_text(item.get('outlet'))}".casefold()
    hits: list[str] = []
    total = 0
    for topic_id, topic in topics_cfg.items():
        topic_hits = sum(keyword_matches(haystack, k) for k in topic.get("keywords", []))
        if topic_hits:
            hits.append(topic_id)
            total += topic_hits
    return hits, total


def find_fis_match(candidates: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    target = norm_title(title)
    exact = [c for c in candidates if norm_title(c.get("title")) == target]
    if exact:
        return exact[0]
    # Limited punctuation/subtitle fallback, still only among FIS records.
    if len(target) >= 24:
        partial = [
            c for c in candidates
            if target in norm_title(c.get("title")) or norm_title(c.get("title")) in target
        ]
        if len(partial) == 1:
            return partial[0]
    return None


def build_person(
    person: dict[str, Any], pure: dict[str, Any], fis: dict[str, Any], cfg: dict[str, Any]
) -> dict[str, Any]:
    min_year = int(cfg.get("min_year", 2018))
    max_outputs = int(cfg.get("max_outputs_per_person", 12))
    topics_cfg = cfg.get("topics", {})

    aliases = set(person.get("pure_names", [])) | {norm_text(person.get("name_en"))}
    doi_index = pure_doi_index(pure, aliases, min_year) if pure else {}
    candidates = fis_candidates(
        fis,
        norm_text(person.get("name_ko")),
        min_year,
        doi_index,
    )

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()

    # Curated order is retained, but a pinned item is shown only if it exists in FIS.
    for rank, pin in enumerate(person.get("pinned", []), start=1):
        match = find_fis_match(candidates, pin.get("title", ""))
        if not match:
            print(
                f"Warning: pinned output not found in FIS for {person.get('name_ko')}: "
                f"{pin.get('title', '')}"
            )
            continue
        record = {
            **match,
            "topics": list(pin.get("topics", [])),
            "featured": True,
            "featuredRank": rank,
        }
        key = norm_title(record.get("title"))
        if key:
            selected.append(record)
            selected_keys.add(key)

    # Fill with recent on-topic FIS publications. Pure cannot introduce candidates here.
    allowed_person_topics = set(person.get("topics", []))
    auto: list[dict[str, Any]] = []
    for item in candidates:
        key = norm_title(item.get("title"))
        if not key or key in selected_keys:
            continue
        item_topics, keyword_score = keyword_topics(item, topics_cfg)
        item_topics = [t for t in item_topics if t in allowed_person_topics]
        if not item_topics:
            continue
        auto.append({
            **item,
            "topics": item_topics,
            "featured": False,
            "featuredRank": None,
            "_score": keyword_score * 100 + int(item.get("year") or 0),
        })

    auto.sort(
        key=lambda x: (x.get("_score", 0), x.get("year", 0), x.get("title", "")),
        reverse=True,
    )
    for item in auto:
        if len(selected) >= max_outputs:
            break
        item.pop("_score", None)
        selected.append(item)

    selected.sort(
        key=lambda x: (
            1 if x.get("featured") else 0,
            -(x.get("featuredRank") or 999),
            int(x.get("year") or 0),
        ),
        reverse=True,
    )

    return {
        "id": norm_text(person.get("id")),
        "nameKo": norm_text(person.get("name_ko")),
        "nameEn": norm_text(person.get("name_en")),
        "role": norm_text(person.get("role")),
        "fields": norm_text(person.get("fields")),
        "office": norm_text(person.get("office")),
        "image": norm_text(person.get("image")),
        "labUrl": norm_text(person.get("lab_url")),
        "profileUrl": norm_text(person.get("profile_url")),
        "areaStatus": norm_text(person.get("area_status") or "core"),
        "topics": list(person.get("topics", [])),
        "outputs": selected,
    }


def payload_without_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(payload)
    clone.pop("generatedAt", None)
    return clone


def write_if_changed(path: Path, payload: dict[str, Any]) -> None:
    old = None
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            old = None
    if old is not None and payload_without_generated_at(old) == payload_without_generated_at(payload):
        print(f"No substantive change: {path}")
        return
    payload["generatedAt"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    cfg = load_config()
    fis_path = Path(cfg.get("fis_path", "data/fis_publications_all.json"))
    pure_path = Path(cfg.get("pure_path", "data/pure_publications_2000plus.json"))

    # FIS is required because it defines publication membership.
    fis = load_json(fis_path, required=True)
    # Pure is optional enrichment only; the page can still build without it.
    pure = load_json(pure_path, required=False)

    people = [build_person(person, pure, fis, cfg) for person in cfg.get("faculty", [])]
    payload = {
        "title": PAGE_TITLE,
        "sourceNote": (
            "Publication membership is based on Yonsei FIS. Yonsei Pure is used only "
            "to enrich exact-title matches with DOI URLs; it does not add publications."
        ),
        "topics": {k: v.get("label", k) for k, v in cfg.get("topics", {}).items()},
        "people": people,
    }
    write_if_changed(Path(cfg.get("output_path", DEFAULT_OUTPUT_PATH)), payload)
    print(f"Done: {len(people)} faculty profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
