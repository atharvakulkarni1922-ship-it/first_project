
import sqlite3
from pathlib import Path

# Project folders
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "leads.db"


def get_connection():
    """Create the data folder and connect to the SQLite database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the initial database tables."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                published TEXT,
                source TEXT,
                url TEXT UNIQUE,
                industry TEXT,
                geography TEXT,
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS lead_classification (
                article_id INTEGER PRIMARY KEY,
                lead_score INTEGER DEFAULT 0,
                lead_priority TEXT DEFAULT 'Monitor',
                reason TEXT,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        """)


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized successfully: {DB_PATH}")

