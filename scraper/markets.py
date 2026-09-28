"""국가별 아마존 사이트 정보."""

from __future__ import annotations

MARKETS: dict[str, dict] = {
    "US": {"name": "미국", "domain": "www.amazon.com", "accept_language": "en-US,en;q=0.9"},
    "UK": {"name": "영국", "domain": "www.amazon.co.uk", "accept_language": "en-GB,en;q=0.9"},
    "DE": {"name": "독일", "domain": "www.amazon.de", "accept_language": "de-DE,de;q=0.9,en;q=0.8"},
    "FR": {"name": "프랑스", "domain": "www.amazon.fr", "accept_language": "fr-FR,fr;q=0.9,en;q=0.8"},
    "IT": {"name": "이탈리아", "domain": "www.amazon.it", "accept_language": "it-IT,it;q=0.9,en;q=0.8"},
    "ES": {"name": "스페인", "domain": "www.amazon.es", "accept_language": "es-ES,es;q=0.9,en;q=0.8"},
}


def bestseller_url(country: str, slug: str, page: int) -> str:
    domain = MARKETS[country]["domain"]
    if page == 1:
        return f"https://{domain}/gp/bestsellers/{slug}"
    return f"https://{domain}/gp/bestsellers/{slug}/ref=zg_bs_pg_{page}_{slug}?ie=UTF8&pg={page}"
