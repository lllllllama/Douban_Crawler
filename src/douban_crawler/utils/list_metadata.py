from __future__ import annotations

import re
from typing import Any

from douban_crawler.utils.text import clean_text


YEAR_RE = re.compile(r"(?:^|[\s/])((?:18|19|20)\d{2})(?=\s|/|\(|$)")
RELEASE_MARKER_RE = re.compile(r"^(?:\(.+\)|(?:18|19|20)\d{2}(?:\(.+\))?)$")


def parse_list_people_info(people_info: Any) -> dict[str, Any]:
    text = clean_text(str(people_info or ""))
    parsed: dict[str, Any] = {
        "year": None,
        "country": "",
        "genres": [],
        "directors": [],
        "actors": [],
    }
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return parsed

    year_match = YEAR_RE.search(text)
    year_start = year_match.start(1) if year_match else len(text)
    year_end = year_match.end(1) if year_match else len(text)
    if year_match:
        parsed["year"] = int(year_match.group(1))

    people_part = text[:year_start].strip(" /")
    tail_part = text[year_end:].strip(" /")

    director_part = ""
    actor_part = ""
    if "导演:" in people_part:
        director_part = people_part.split("导演:", 1)[1]
        if "主演:" in director_part:
            director_part, actor_part = director_part.split("主演:", 1)
    elif "主演:" in people_part:
        actor_part = people_part.split("主演:", 1)[1]

    parsed["directors"] = split_people_names(director_part)
    parsed["actors"] = split_people_names(actor_part)

    tail_parts = [
        part
        for part in (clean_text(part) for part in tail_part.split("/"))
        if part and not RELEASE_MARKER_RE.match(part)
    ]
    if tail_parts:
        parsed["country"] = tail_parts[0]
    if len(tail_parts) >= 2:
        parsed["genres"] = [item for item in re.split(r"\s+", tail_parts[1]) if item]

    return parsed


def split_people_names(value: Any, *, limit: int = 8) -> list[str]:
    text = clean_text(str(value or ""))
    text = text.replace("...", "").replace("…", "")
    names = [clean_text(item) for item in re.split(r"\s*/\s*", text) if clean_text(item)]
    return names[:limit]
