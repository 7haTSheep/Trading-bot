"""Checking whether a newer QuickScan has been released.

Asks GitHub for the repository's latest release and compares its tag against
the running version. Nothing is downloaded and nothing is installed: the app
offers to open the release page and the user decides. That is deliberate.

Replacing a running program on Windows is not a thing an application can do to
itself -- the executable and its DLLs are locked while it runs -- so a
self-updater would have to write a helper, exit, and trust the helper to
finish. When that goes wrong it leaves a half-replaced installation and no
working program to explain what happened. Opening a page cannot fail that way.

Uses urllib rather than requests so the bundle gains no dependency for one
HTTP call a day.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple

TIMEOUT_SECONDS = 6
API = 'https://api.github.com/repos/{repo}/releases/latest'


@dataclass(frozen=True)
class Release:
    version: str            # as published, e.g. "v1.1.0"
    name: str
    notes: str
    url: str


def parse_version(text: str) -> Tuple[int, ...]:
    """Turn a tag such as 'v1.2.3' into (1, 2, 3).

    Anything non-numeric is dropped rather than guessed at, so a tag like
    '1.2.0-beta' compares equal to '1.2.0'. Ranking prereleases correctly
    needs the full precedence rules and this project has no prereleases;
    inventing a scheme now would only be a thing to get wrong later.
    """
    numbers = re.findall(r'\d+', text or '')
    return tuple(int(n) for n in numbers) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    """True when candidate is a strictly later version than current."""
    left, right = parse_version(candidate), parse_version(current)
    # Compare on equal length so 1.2 and 1.2.0 are the same version.
    length = max(len(left), len(right))
    left += (0,) * (length - len(left))
    right += (0,) * (length - len(right))
    return left > right


def latest_release(repo: str, timeout: int = TIMEOUT_SECONDS) -> Optional[Release]:
    """The repository's newest release, or None if there is not one.

    Returns None rather than raising for every expected failure: no releases
    published yet, no network, GitHub rate-limiting an unauthenticated
    caller. An update check that interrupts the user because their wifi
    dropped is worse than one that quietly tries again tomorrow.
    """
    request = urllib.request.Request(
        API.format(repo=repo),
        headers={
            # GitHub rejects unauthenticated calls that do not identify
            # themselves.
            'User-Agent': 'QuickScan-update-check',
            'Accept': 'application/vnd.github+json',
        })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    tag = payload.get('tag_name')
    if not tag or payload.get('draft'):
        return None

    return Release(
        version=str(tag),
        name=str(payload.get('name') or tag),
        notes=str(payload.get('body') or '').strip(),
        url=str(payload.get('html_url')
                or f'https://github.com/{repo}/releases/latest'),
    )


def check(current: str, repo: str, timeout: int = TIMEOUT_SECONDS) -> Optional[Release]:
    """The newest release if it is later than current, otherwise None."""
    release = latest_release(repo, timeout)
    if release is None or not is_newer(release.version, current):
        return None
    return release
