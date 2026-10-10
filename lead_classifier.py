
import re
from database import get_connection, initialize_database


# Strong signals: directly related to conveyor opportunities
STRONG_SIGNALS = {
    "conveyor": 25,
    "belt conveyor": 25,
    "conveyor system": 25,
    "material handling": 20,
    "bulk handling": 20,
    "bulk material": 20,
    "stacker reclaimer": 25,
    "EPC contract": 20,
    "handling system": 15,
}

# Signals that indicate a possible industrial project
PROJECT_SIGNALS = {
    "new plant": 20,
    "greenfield": 20,
    "expansion": 15,
    "capacity expansion": 20,
    "construction": 12,
    "commissioning": 10,
    "project awarded": 20,
    "contract awarded": 20,
    "tender": 15,
    "feasibility": 8,
    "investment": 10,
    "mine development": 15,
    "plant development": 15,
}

INDUSTRIAL_SECTORS = {
    "mining": 12,
    "coal": 10,
    "steel": 10,
    "cement": 10,
    "iron ore": 12,
    "power plant": 10,
    "thermal power": 10,
    "port": 8,
    "fertilizer": 8,
    "aluminium": 8,
    "bauxite": 10,
    "limestone": 8,
}

NEGATIVE_SIGNALS = [
    "job vacancy",
    "recruitment",
    "apprenticeship",
    "sports",
    "share price",
    "stock market",
    "celebrity",
    "crime investigation",
    "scrap theft",
]


def score_article(title, industry, geography):
    text = f"{title} {industry or ''}".lower()
    score = 0
    reasons = []

    for keyword, points in STRONG_SIGNALS.items():
        if keyword in text:
            score += points
            reasons.append(f"{keyword}: +{points}")

    for keyword, points in PROJECT_SIGNALS.items():
        if keyword in text:
            score += points
            reasons.append(f"{keyword}: +{points}")

    for keyword, points in INDUSTRIAL_SECTORS.items():
        if keyword in text:
            score += points
            reasons.append(f"{keyword}: +{points}")

    # Prefer India-related opportunities for the initial dashboard.
    if (geography or "").lower() == "india":
        score += 5
        reasons.append("India focus: +5")

    # Reduce scores for likely irrelevant news.
    for keyword in NEGATIVE_SIGNALS:
        if keyword in text:
            score -= 35
            reasons.append(f"Irrelevant-news signal '{keyword}': -35")

    score = max(0, min(score, 100))

    if any(keyword in text for keyword in NEGATIVE_SIGNALS):
        priority = "Review / Exclude"
    elif score >= 60:
        priority = "High Potential"
    elif score >= 35:
        priority = "Potential"
    else:
        priority = "Monitor"

    reason = "; ".join(reasons) if reasons else "No strong project signals found"

    return score, priority, reason


def classify_articles():
    initialize_database()

    with get_connection() as connection:
        articles = connection.execute("""
            SELECT id, title, industry, geography
            FROM articles
        """).fetchall()

        for article in articles:
            score, priority, reason = score_article(
                article["title"],
                article["industry"],
                article["geography"],
            )

            connection.execute("""
                INSERT INTO lead_classification
                    (article_id, lead_score, lead_priority, reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    lead_score = excluded.lead_score,
                    lead_priority = excluded.lead_priority,
                    reason = excluded.reason
            """, (
                article["id"],
                score,
                priority,
                reason,
            ))

        results = connection.execute("""
            SELECT lead_priority, COUNT(*) AS total
            FROM lead_classification
            GROUP BY lead_priority
            ORDER BY COUNT(*) DESC
        """).fetchall()

    print(f"\nClassified {len(articles)} articles.")
    print("\nPriority summary:")

    for result in results:
        print(f"{result['lead_priority']}: {result['total']}")


if __name__ == "__main__":
    classify_articles()

