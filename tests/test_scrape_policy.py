import pytest

from wcdrawlab.scraping import ScrapePolicy, ScrapePolicyError


def test_allowlist_blocks_unknown_domain():
    policy = ScrapePolicy(allowed_domains={"fifa.com"})
    policy.validate_url("https://fifa.com/news")
    with pytest.raises(ScrapePolicyError):
        policy.validate_url("https://example.com/news")
