from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib import robotparser

import requests
import yaml


class ScrapePolicyError(PermissionError):
    """Raised when a fetch violates the project's source-governance policy."""


@dataclass(frozen=True)
class ScrapePolicy:
    allowed_domains: set[str]
    respect_robots_txt: bool = True
    max_requests_per_minute_per_domain: int = 12
    cache_ttl_seconds: int = 900
    forbid_login: bool = True
    forbid_paywall_bypass: bool = True
    forbid_captcha_bypass: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ScrapePolicy":
        raw = yaml.safe_load(Path(path).read_text())
        rules = raw.get("rules", {})
        return cls(
            allowed_domains=set(raw.get("allowed_domains", [])),
            respect_robots_txt=bool(rules.get("respect_robots_txt", True)),
            max_requests_per_minute_per_domain=int(rules.get("max_requests_per_minute_per_domain", 12)),
            cache_ttl_seconds=int(rules.get("cache_ttl_seconds", 900)),
            forbid_login=bool(rules.get("forbid_login", True)),
            forbid_paywall_bypass=bool(rules.get("forbid_paywall_bypass", True)),
            forbid_captcha_bypass=bool(rules.get("forbid_captcha_bypass", True)),
        )

    def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"}:
            raise ScrapePolicyError("Only http/https URLs are allowed.")
        domain = parsed.netloc.split(":")[0].lower()
        if domain not in self.allowed_domains and not any(domain.endswith("." + d) for d in self.allowed_domains):
            raise ScrapePolicyError(f"Domain {domain!r} is not allowlisted. Create a data request and get approval first.")


class SafeFetcher:
    """Low-volume, cached, robots-aware fetcher for approved public pages only."""

    def __init__(self, policy: ScrapePolicy, cache_dir: str | Path = "data/cache/scrape") -> None:
        self.policy = policy
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request: dict[str, float] = {}

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        try:
            rp.read()
            return rp.can_fetch("wcdrawlab", url)
        except Exception:
            # Fail closed for a policy that promises robots compliance.
            return False

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.html"

    def get_text(self, url: str, timeout: float = 20.0) -> str:
        self.policy.validate_url(url)
        if self.policy.respect_robots_txt and not self._robots_allowed(url):
            raise ScrapePolicyError(f"robots.txt does not permit this fetch: {url}")
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        interval = 60.0 / max(1, self.policy.max_requests_per_minute_per_domain)
        elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
        if elapsed < interval:
            time.sleep(interval - elapsed)

        cache_path = self._cache_path(url)
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime <= self.policy.cache_ttl_seconds:
            return cache_path.read_text(encoding="utf-8", errors="replace")

        resp = requests.get(url, headers={"User-Agent": "wcdrawlab/0.2 public-data-research"}, timeout=timeout)
        self._last_request[domain] = time.monotonic()
        resp.raise_for_status()
        cache_path.write_text(resp.text, encoding="utf-8")
        return resp.text
