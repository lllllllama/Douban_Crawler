from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

from douban_crawler.config import POSTER_DIR
from douban_crawler.utils.text import slugify


def poster_filename(rank: int | None, title: str, poster_url: str) -> str:
    suffix = Path(urlparse(poster_url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    prefix = f"{rank:03d}_" if rank else ""
    return f"{prefix}{slugify(title)[:80]}{suffix}"


def download_poster(
    poster_url: str,
    *,
    title: str,
    rank: int | None = None,
    session: requests.Session | None = None,
    output_dir: Path = POSTER_DIR,
    timeout: tuple[float, float] = (5.0, 30.0),
) -> str:
    """Download a poster with a small resume-friendly .part file.

    The function is intentionally conservative: if the final file already
    exists and is non-empty, it is treated as cached and returned immediately.
    """

    poster_url = poster_url.strip()
    if not poster_url:
        return ""

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / poster_filename(rank, title, poster_url)
    if target.exists() and target.stat().st_size > 0:
        return str(target)

    partial = target.with_suffix(target.suffix + ".part")
    existing_size = partial.stat().st_size if partial.exists() else 0
    headers = {"Referer": "https://movie.douban.com/"}
    if existing_size:
        headers["Range"] = f"bytes={existing_size}-"

    client = session or requests.Session()
    response = client.get(poster_url, headers=headers, stream=True, timeout=timeout)
    if response.status_code not in {200, 206}:
        response.raise_for_status()

    mode = "ab" if existing_size and response.status_code == 206 else "wb"
    with partial.open(mode + "") as fp:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                fp.write(chunk)

    partial.replace(target)
    return str(target)
