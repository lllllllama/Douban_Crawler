from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


def build_robot_parser(base_url: str) -> RobotFileParser:
    parsed = urlparse(base_url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.read()
    return parser


def is_allowed(parser: RobotFileParser, url: str, user_agent: str) -> bool:
    return parser.can_fetch(user_agent, url)
