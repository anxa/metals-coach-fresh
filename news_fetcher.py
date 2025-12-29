"""
MetalsDaily News Scraper

Fetches precious metals news headlines from MetalsDaily.com.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re

NEWS_URLS = {
    "gold": "https://www.metalsdaily.com/news/gold-news/",
    "silver": "https://www.metalsdaily.com/news/silver-news/",
    "pgm": "https://www.metalsdaily.com/news/pgm-news/",
}

METAL_EMOJIS = {
    "gold": "🥇",
    "silver": "🥈",
    "pgm": "⚪",
}


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from format DD-MM-YY."""
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%y")
    except Exception:
        return None


def fetch_news(metal: str, limit: int = 5) -> List[Dict]:
    """
    Fetch news headlines for a metal.

    Args:
        metal: "gold", "silver", or "pgm"
        limit: Maximum number of headlines to return

    Returns:
        List of dicts with: title, url, date, date_str, metal, emoji
    """
    url = NEWS_URLS.get(metal)
    if not url:
        return []

    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MetalsCoach/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        items = []
        seen_titles = set()  # Avoid duplicates

        # Find news links (structure: <a href="...">HEADLINE TEXT DD-MM-YY</a>)
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)

            # Match date pattern at end: DD-MM-YY
            match = re.search(r'(\d{2}-\d{2}-\d{2})$', text)
            if match:
                date_str = match.group(1)
                title = text[:-len(date_str)].strip()

                # Skip short/empty titles and duplicates
                if not title or len(title) < 10:
                    continue
                if title in seen_titles:
                    continue

                seen_titles.add(title)

                # Build full URL if relative
                href = link['href']
                if not href.startswith('http'):
                    href = f"https://www.metalsdaily.com{href}"

                items.append({
                    "title": title,
                    "url": href,
                    "date": parse_date(date_str),
                    "date_str": date_str,
                    "metal": metal,
                    "emoji": METAL_EMOJIS.get(metal, "📰"),
                })

                if len(items) >= limit:
                    break

        return items

    except Exception as e:
        print(f"Error fetching {metal} news: {e}")
        return []


def fetch_all_news(limit_per_metal: int = 4) -> List[Dict]:
    """
    Fetch news from all sources and return combined, sorted by date.

    Args:
        limit_per_metal: Max headlines per metal category

    Returns:
        Combined list of news items, sorted newest first
    """
    all_news = []
    for metal in NEWS_URLS.keys():
        all_news.extend(fetch_news(metal, limit_per_metal))

    # Sort by date (newest first), handle None dates
    all_news.sort(key=lambda x: x['date'] or datetime.min, reverse=True)
    return all_news


if __name__ == "__main__":
    print("=== MetalsDaily News Fetcher Test ===\n")

    for metal in NEWS_URLS.keys():
        print(f"\n--- {metal.upper()} ---")
        items = fetch_news(metal, limit=3)
        for item in items:
            print(f"  {item['emoji']} {item['title'][:60]}... ({item['date_str']})")

    print("\n\n=== Combined Feed ===")
    all_items = fetch_all_news(limit_per_metal=3)
    for item in all_items[:10]:
        print(f"  {item['emoji']} [{item['metal'].upper()}] {item['title'][:50]}... ({item['date_str']})")

    print(f"\nTotal items: {len(all_items)}")
