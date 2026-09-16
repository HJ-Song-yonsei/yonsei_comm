#!/usr/bin/env python3
"""Build the Crisis & Strategic Communication people/research feed."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("config/crisis_people.yml")
SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^0-9a-z가-힣]+", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def norm_title(value: Any) -> str:
    text = norm_text(value).casefold()
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
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


def pure_candidates(pure: dict[str, Any], aliases: set[str], min_year: int) -> list[dict[str, Any]]:
    out = []
    alias_fold = {a.casefold() for a in aliases}
    for item in pure.get("items", []):
        year = year_from_item(item)
        if year < min_year:
            continue
        authors = [norm_text(a) for a in item.get("authors", [])]
        if not any(a.casefold() in alias_fold for a in authors):
            continue
        out.append({
            "year": year,
            "title": norm_text(item.get("title")),
            "outlet": norm_text(item.get("outlet")),
            "url": doi_url(item.get("doi")) or norm_text(item.get("link")),
            "source": "Pure",
        })
    return out


def fis_candidates(fis: dict[str, Any], faculty_name: str, min_year: int) -> list[dict[str, Any]]:
    out = []
    for item in fis.get("items", []):
        if norm_text(item.get("faculty")) != faculty_name:
            continue
        year = year_from_item(item)
        if year < min_year:
            continue
        out.append({
            "year": year,
            "title": norm_text(item.get("title")),
            "outlet": norm_text(item.get("journal")),
            "url": norm_text(item.get("publicationUrl")),
            "source": "FIS",
        })
    return out


def dedupe_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {}
    for item in items:
        key = norm_title(item.get("title"))
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(item)
            continue
        old = merged[key]
        if not old.get("url") and item.get("url"):
            old["url"] = item["url"]
        if not old.get("outlet") and item.get("outlet"):
            old["outlet"] = item["outlet"]
        sources = {s for s in norm_text(old.get("source")).split("+") if s}
        sources.add(norm_text(item.get("source")))
        old["source"] = "+".join(sorted(sources))
        old["year"] = max(int(old.get("year") or 0), int(item.get("year") or 0))
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
    hits, total = [], 0
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
        return exact[0]
    if len(target) >= 24:
        partial = [c for c in candidates
                   if target in norm_title(c.get("title"))
                   or norm_title(c.get("title")) in target]
        if partial:
            return partial[0]
    return None


def build_person(person: dict[str, Any], pure: dict[str, Any], fis: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    min_year = int(cfg.get("min_year", 2018))
    max_outputs = int(cfg.get("max_outputs_per_person", 12))
    topics_cfg = cfg.get("topics", {})

    aliases = set(person.get("pure_names", [])) | {norm_text(person.get("name_en"))}
    candidates = dedupe_candidates(
        pure_candidates(pure, aliases, min_year)
        + fis_candidates(fis, norm_text(person.get("name_ko")), min_year)
    )

    selected, selected_keys = [], set()

    for rank, pin in enumerate(person.get("pinned", []), start=1):
        match = find_source_match(candidates, pin.get("title", ""))
        record = {
            "year": int(pin.get("year") or (match or {}).get("year") or 0),
            "title": norm_text(pin.get("title") or (match or {}).get("title")),
            "outlet": norm_text((match or {}).get("outlet") or pin.get("outlet")),
            "url": norm_text((match or {}).get("url") or pin.get("url")),
            "topics": list(pin.get("topics", [])),
            "featured": True,
            "featuredRank": rank,
            "source": norm_text((match or {}).get("source") or "curated"),
        }
        key = norm_title(record["title"])
        if key:
            selected.append(record)
            selected_keys.add(key)

    allowed = set(person.get("topics", []))
    auto = []
    for item in candidates:
        key = norm_title(item.get("title"))
        if not key or key in selected_keys:
            continue
        item_topics, score = keyword_topics(item, topics_cfg)
        item_topics = [t for t in item_topics if t in allowed]
        if not item_topics:
            continue
        auto.append({
            **item,
            "topics": item_topics,
            "featured": False,
            "featuredRank": None,
            "_score": score * 100 + int(item.get("year") or 0),
        })

    auto.sort(key=lambda x: (x["_score"], x.get("year", 0), x.get("title", "")), reverse=True)
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


def payload_without_generated_at(payload):
    clone = copy.deepcopy(payload)
    clone.pop("generatedAt", None)
    return clone


def write_if_changed(path: Path, payload: dict[str, Any]):
    old = None
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if old is not None and payload_without_generated_at(old) == payload_without_generated_at(payload):
        print(f"No substantive change: {path}")
        return
    payload["generatedAt"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated: {path}")


def main():
    cfg = load_config()
    pure = load_json(Path(cfg.get("pure_path")), required=True)
    fis = load_json(Path(cfg.get("fis_path")), required=False)

    people = [build_person(p, pure, fis, cfg) for p in cfg.get("faculty", [])]
    payload = {
        "title": "People in Crisis & Strategic Communication",
        "sourceNote": "Selected outputs are drawn from Yonsei Pure and FIS, with curated representative outputs retained through the configuration file.",
        "topics": {k: v.get("label", k) for k, v in cfg.get("topics", {}).items()},
        "people": people,
    }
    write_if_changed(Path(cfg.get("output_path")), payload)
    print(f"Done: {len(people)} faculty profiles")


if __name__ == "__main__":
    main()
