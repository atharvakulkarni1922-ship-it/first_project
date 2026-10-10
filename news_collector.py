
import feedparser
import requests
import sqlite3
from urllib.parse import quote_plus
from datetime import datetime, timezone

from database import get_connection, initialize_database


SEARCH_QUERIES = {
    "Mining": '"mining project" OR "mine expansion" conveyor India',
    "Steel": '"steel plant" expansion India',
    "Cement": '"cement plant" expansion India',
    "Power": '"thermal power plant" India project',
    "Ports": '"bulk material handling" port India',
    "Conveyors": '"conveyor system" OR "belt conveyor" project India',
    "EPC Contracts": '"material handling system" EPC contract India',
}


def collect_news():
    initialize_database()
    total_new = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; IndustrialLeadResearch/1.0)"
    }

    with get_connection() as connection:
        for industry, query in SEARCH_QUERIES.items():
            print(f"\nSearching: {industry}")

            
            url = (
                  "https://news.google.com/rss/search?q="
                  + quote_plus(f"{query} when:7d")
                  + "&hl=en-IN&gl=IN&ceid=IN:en"
         )


            try:
                response = requests.get(
                    url, headers=headers, timeout=20
                )
                response.raise_for_status()
                feed = feedparser.parse(response.content)

            except requests.RequestException as error:
                print(f"Could not retrieve {industry} news: {error}")
                continue

            for entry in feed.entries:
                title = entry.get("title", "").strip()
                article_url = entry.get("link", "").strip()

                if not title or not article_url:
                    continue

                published = entry.get("published", "")
                source = entry.get("source", {}).get("title", "")

                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO articles
                    (title, published, source, url, industry, geography)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        published,
                        source,
                        article_url,
                        industry,
                        "India",
                    ),
                )

                if cursor.rowcount > 0:
                    total_new += 1

            print(f"Retrieved {len(feed.entries)} news items")

    print(f"\nCollection complete. New articles saved: {total_new}")
    print("Run again later to collect newly published articles.")


if __name__ == "__main__":
    collect_news()

