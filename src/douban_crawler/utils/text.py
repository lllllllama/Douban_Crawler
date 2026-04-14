from __future__ import annotations

import re


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip(" /")


def slugify(value: str) -> str:
    value = clean_text(value)
    return re.sub(r'[\\\\/:*?"<>|]+', "_", value)
