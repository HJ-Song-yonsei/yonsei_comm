#!/usr/bin/env python3
"""Build a research-area people/output feed with Pure as the primary source.

Display policy
--------------
- Yonsei Pure is the primary source for displayed publications.
- FIS is used only to supplement Korean-language articles (titles containing Hangul).
- At most one Korean-language article is retained in each faculty member's display pool.
- If a Korean article is available, it is assigned display priority 3 so the existing
  page renderer shows up to two Pure outputs plus one Korean output.
- If no Korean article is available, the visible outputs are all Pure-based.
- When the same Korean article exists in both Pure and FIS, Pure bibliographic data
  and DOI/link are preferred; FIS supplies the domestic/Korean-language signal.
- Faculty explicitly marked allow_curated_fallback may temporarily use pinned config
  metadata when a pinned publication is not yet available in Pure/FIS. A later source
  match automatically replaces the curated fallback.
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
HANGUL_RE = re.compile(r"[가-힣]")
DOMESTIC_LABEL = "국내논문"


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


def has_hangul(value: Any) -> bool:
    return HANGUL_RE.search(norm_text(value)) is not None


def domestic_outlet_label(outlet: Any) -> str:
    text = norm_text(outlet)
    if not text:
        return DOMESTIC_LABEL
    if DOMESTIC_LABEL in text:
        return text
    return f"{text} · {DOMESTIC_LABEL}"


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


def dedupe_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        key = norm_title(item.get("title"))
        if not key:
            continue
        old = merged.get(key)
        if old is None:
            merged[key] = dict(item)
            continue
        if int(item.get("year") or 0) > int(old.get("year") or 0):
            merged[key] = dict(item)
            old = merged[key]
        if not old.get("url") and item.get("url"):
            old["url"] = item.get("url", "")
            old["urlSource"] = item.get("urlSource", "")
        if not old.get("outletRaw") and item.get("outletRaw"):
            old["outletRaw"] = item.get("outletRaw", "")
            old["outlet"] = item.get("outlet", "")
    return list(merged.values())


def pure_candidates(
    pure: dict[str, Any], aliases: set[str], min_year: int
) -> list[dict[str, Any]]:
    """Return all eligible Pure publications for one faculty member."""
    alias_fold = {a.casefold() for a in aliases if a}
    out: list[dict[str, Any]] = []
    for item in pure.get("items", []):
        year = year_from_item(item)
        if year < min_year:
            continue
        authors = [norm_text(a) for a in item.get("authors", [])]
        if not any(a.casefold() in alias_fold for a in authors):
            continue

        title = norm_text(item.get("title"))
        if not title:
            continue
        korean = has_hangul(title)
        outlet = norm_text(item.get("outlet"))
        out.append({
            "year": year,
            "title": title,
            "outletRaw": outlet,
            "outlet": domestic_outlet_label(outlet) if korean else outlet,
            "url": doi_url(item.get("doi")) or norm_text(item.get("link")),
            "urlSource": "Pure DOI" if norm_text(item.get("doi")) else ("Pure" if item.get("link") else ""),
            "source": "Pure",
            "publicationType": "domestic" if korean else "international",
            "classificationReason": "hangul_article_title" if korean else "pure_primary",
            "isKoreanTitle": korean,
        })
    return dedupe_candidates(out)


def fis_korean_candidates(
    fis: dict[str, Any], faculty_name: str, min_year: int
) -> list[dict[str, Any]]:
    """Return only FIS articles whose titles contain Hangul."""
    out: list[dict[str, Any]] = []
    for item in fis.get("items", []):
        if norm_text(item.get("faculty")) != faculty_name:
            continue
        year = year_from_item(item)
        if year < min_year:
            continue
        title = norm_text(item.get("title"))
        if not title or not has_hangul(title):
            continue
        outlet = norm_text(item.get("journal"))
        out.append({
            "year": year,
            "title": title,
            "outletRaw": outlet,
            "outlet": domestic_outlet_label(outlet),
            "url": norm_text(item.get("publicationUrl")),
            "urlSource": "FIS" if item.get("publicationUrl") else "",
            "source": "FIS",
            "publicationType": "domestic",
            "classificationReason": "hangul_article_title",
            "isKoreanTitle": True,
        })
    return dedupe_candidates(out)


def merge_pure_with_korean_fis(
    pure_items: list[dict[str, Any]], fis_korean: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pure defines the base pool; FIS can add/flag Korean-language articles only."""
    merged: dict[str, dict[str, Any]] = {
        norm_title(item.get("title")): dict(item)
        for item in pure_items
        if norm_title(item.get("title"))
    }

    for fis_item in fis_korean:
        key = norm_title(fis_item.get("title"))
        if not key:
            continue
        pure_item = merged.get(key)
        if pure_item is None:
            merged[key] = dict(fis_item)
            continue

        # Same article in both feeds: retain Pure metadata/DOI, but mark it as
        # the Korean/domestic item and fall back to FIS fields if Pure is blank.
        pure_item["isKoreanTitle"] = True
        pure_item["publicationType"] = "domestic"
        pure_item["classificationReason"] = "hangul_article_title"
        pure_item["source"] = "Pure+FIS"
        raw_outlet = pure_item.get("outletRaw") or fis_item.get("outletRaw") or ""
        pure_item["outletRaw"] = raw_outlet
        pure_item["outlet"] = domestic_outlet_label(raw_outlet)
        if not pure_item.get("url") and fis_item.get("url"):
            pure_item["url"] = fis_item.get("url", "")
            pure_item["urlSource"] = fis_item.get("urlSource", "")

    return list(merged.values())



def curated_fallback_record(pin: dict[str, Any]) -> dict[str, Any]:
    """Convert one pinned config item into a temporary source record.

    This is used only when the faculty entry explicitly opts in with
    allow_curated_fallback: true and no matching Pure/Korean-FIS record exists.
    """
    title = norm_text(pin.get("title"))
    outlet = norm_text(pin.get("outlet"))
    korean = has_hangul(title)
    return {
        "year": int(pin.get("year") or 0),
        "title": title,
        "outletRaw": outlet,
        "outlet": domestic_outlet_label(outlet) if korean else outlet,
        "url": norm_text(pin.get("url")),
        "urlSource": "curated" if pin.get("url") else "",
        "source": "curated",
        "publicationType": "domestic" if korean else "international",
        "classificationReason": "curated_fallback",
        "isKoreanTitle": korean,
    }


def keyword_matches(haystack: str, keyword: str) -> bool:
    kw = norm_text(keyword).casefold()
    if not kw:
        return False
    if has_hangul(kw):
        return kw in haystack
    stem = kw.endswith("*")
    if stem:
        kw = kw[:-1]
    escaped = re.escape(kw).replace(r"\ ", r"\s+")
    suffix = r"[a-z0-9_-]*" if stem else ""
    pattern = rf"(?<![a-z0-9]){escaped}{suffix}(?![a-z0-9])"
    return re.search(pattern, haystack, flags=re.I) is not None


def keyword_topics(item: dict[str, Any], topics_cfg: dict[str, Any]) -> tuple[list[str], int]:
    # Use the raw journal name for classification; the display-only "국내논문"
    # suffix must not create artificial keyword matches.
    haystack = f"{norm_text(item.get('title'))} {norm_text(item.get('outletRaw') or item.get('outlet'))}".casefold()
    hits: list[str] = []
    total = 0
    for topic_id, topic in topics_cfg.items():
        topic_hits = sum(keyword_matches(haystack, k) for k in topic.get("keywords", []))
        if topic_hits:
            hits.append(topic_id)
            total += topic_hits
    return hits, total


def find_source_match(candidates: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    target = norm_title(title)
    exact = [c for c in candidates if norm_title(c.get("title")) == target]
    if exact:
        exact.sort(key=lambda x: 1 if str(x.get("source", "")).startswith("Pure") else 0, reverse=True)
        return exact[0]
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
    pure_items = pure_candidates(pure, aliases, min_year)
    korean_items = fis_korean_candidates(fis, norm_text(person.get("name_ko")), min_year) if fis else []
    candidates = merge_pure_with_korean_fis(pure_items, korean_items)

    # Build curated matches first. Normally a pinned record must be backed by
    # Pure or the Korean-language FIS supplement. For explicitly opted-in faculty
    # (e.g., a newly appointed professor not yet indexed in Pure), pinned config
    # metadata may temporarily serve as the source record.
    pinned_records: list[dict[str, Any]] = []
    pinned_keys: set[str] = set()
    allow_curated_fallback = bool(person.get("allow_curated_fallback", False))
    for pin_rank, pin in enumerate(person.get("pinned", []), start=1):
        match = find_source_match(candidates, pin.get("title", ""))
        if not match and allow_curated_fallback:
            match = curated_fallback_record(pin)
            print(
                f"Info: using curated fallback for {person.get('name_ko')}: "
                f"{pin.get('title', '')}"
            )
        elif not match:
            print(
                f"Warning: pinned output not found in Pure/Korean-FIS for {person.get('name_ko')}: "
                f"{pin.get('title', '')}"
            )
            continue
        record = {
            **match,
            "topics": list(pin.get("topics", [])),
            "featured": True,
            "featuredRank": None,  # assigned after the Korean slot is chosen
            "_pinRank": pin_rank,
            "_score": 100000 - pin_rank,
        }
        key = norm_title(record.get("title"))
        if key and key not in pinned_keys:
            pinned_records.append(record)
            pinned_keys.add(key)

    # Build automatic topic-matched pool. This is primarily Pure; FIS-only
    # candidates can enter only when their titles contain Hangul.
    allowed_person_topics = set(person.get("topics", []))
    auto_records: list[dict[str, Any]] = []
    for item in candidates:
        key = norm_title(item.get("title"))
        if not key or key in pinned_keys:
            continue
        item_topics, keyword_score = keyword_topics(item, topics_cfg)
        item_topics = [t for t in item_topics if t in allowed_person_topics]
        if not item_topics:
            continue
        auto_records.append({
            **item,
            "topics": item_topics,
            "featured": False,
            "featuredRank": None,
            "_pinRank": None,
            "_score": keyword_score * 100 + int(item.get("year") or 0),
        })

    auto_records.sort(
        key=lambda x: (x.get("_score", 0), x.get("year", 0), x.get("title", "")),
        reverse=True,
    )

    # Choose a single Korean-language article for the person's display pool.
    # A curated Korean item wins; otherwise use the strongest recent topic match.
    korean_pinned = [x for x in pinned_records if x.get("isKoreanTitle")]
    korean_auto = [x for x in auto_records if x.get("isKoreanTitle")]
    korean_pick = None
    if korean_pinned:
        korean_pick = sorted(korean_pinned, key=lambda x: int(x.get("_pinRank") or 999))[0]
    elif korean_auto:
        korean_pick = korean_auto[0]

    # All other retained outputs are non-Korean and therefore Pure-derived.
    pure_pinned = [x for x in pinned_records if not x.get("isKoreanTitle")]
    pure_auto = [x for x in auto_records if not x.get("isKoreanTitle")]

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()

    # Preserve curated Pure order. If a Korean article exists, reserve featured
    # rank 3 for it: ranks 1-2 remain Pure, subsequent Pure pins shift to 4+.
    for idx, item in enumerate(pure_pinned, start=1):
        clean = dict(item)
        clean["featured"] = True
        clean["featuredRank"] = idx if (not korean_pick or idx <= 2) else idx + 1
        key = norm_title(clean.get("title"))
        if key and key not in selected_keys:
            selected.append(clean)
            selected_keys.add(key)

    if korean_pick:
        clean = dict(korean_pick)
        clean["featured"] = True
        clean["featuredRank"] = 3
        # Current research HTML displays `outlet` verbatim; appending the label
        # here makes the domestic status visible without changing page templates.
        clean["outletRaw"] = norm_text(clean.get("outletRaw") or clean.get("outlet"))
        clean["outlet"] = domestic_outlet_label(clean.get("outletRaw"))
        clean["publicationType"] = "domestic"
        clean["isKoreanTitle"] = True
        key = norm_title(clean.get("title"))
        if key and key not in selected_keys:
            selected.append(clean)
            selected_keys.add(key)

    # Fill the remainder only with non-Korean Pure records. Thus, if there is no
    # Korean candidate, every automatic item shown comes from Pure.
    for item in pure_auto:
        if len(selected) >= max_outputs:
            break
        key = norm_title(item.get("title"))
        if not key or key in selected_keys:
            continue
        clean = dict(item)
        clean["featured"] = False
        clean["featuredRank"] = None
        selected.append(clean)
        selected_keys.add(key)

    # Keep only max_outputs, but never drop the reserved Korean record. In normal
    # configs (max 12) this is mostly a guard for future changes.
    if len(selected) > max_outputs:
        korean_key = norm_title(korean_pick.get("title")) if korean_pick else ""
        head = selected[:max_outputs]
        if korean_key and not any(norm_title(x.get("title")) == korean_key for x in head):
            head[-1] = next(x for x in selected if norm_title(x.get("title")) == korean_key)
        selected = head

    selected.sort(
        key=lambda x: (
            1 if x.get("featured") else 0,
            -(x.get("featuredRank") or 999),
            int(x.get("year") or 0),
        ),
        reverse=True,
    )

    # Internal ranking helpers should not leak into the JSON feed.
    for item in selected:
        item.pop("_pinRank", None)
        item.pop("_score", None)

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
    pure_path = Path(cfg.get("pure_path", "data/pure_publications_2000plus.json"))
    fis_path = Path(cfg.get("fis_path", "data/fis_publications_all.json"))

    # Pure is required and primary. FIS is optional: if it is temporarily absent,
    # the pages still build entirely from Pure rather than losing output rows.
    pure = load_json(pure_path, required=True)
    fis = load_json(fis_path, required=False)

    people = [build_person(person, pure, fis, cfg) for person in cfg.get("faculty", [])]
    payload = {
        "title": PAGE_TITLE,
        "sourceNote": (
            "Selected outputs are based primarily on Yonsei Pure. Yonsei FIS is used "
            "only to supplement one relevant Korean-language article per faculty member "
            "when available; otherwise displayed outputs are Pure-based."
        ),
        "topics": {k: v.get("label", k) for k, v in cfg.get("topics", {}).items()},
        "people": people,
    }
    write_if_changed(Path(cfg.get("output_path", DEFAULT_OUTPUT_PATH)), payload)
    print(f"Done: {len(people)} faculty profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
