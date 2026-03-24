"""
Storage layer using SQLite for persistence and resumability.
Stores crawl jobs, pages, the crawl queue, and word frequencies
so the system can resume after interruption without starting from scratch.
"""

import aiosqlite
import time
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "crawler.db")


class Storage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Create database connection and tables."""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA synchronous=NORMAL")
        await self._create_tables()

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                max_depth INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                pages_crawled INTEGER NOT NULL DEFAULT 0,
                pages_failed INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                job_id INTEGER NOT NULL,
                origin TEXT NOT NULL,
                depth INTEGER NOT NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                FOREIGN KEY (job_id) REFERENCES crawl_jobs(id),
                UNIQUE(url, job_id)
            );

            CREATE TABLE IF NOT EXISTS crawl_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                job_id INTEGER NOT NULL,
                depth INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                FOREIGN KEY (job_id) REFERENCES crawl_jobs(id),
                UNIQUE(url, job_id)
            );

            CREATE TABLE IF NOT EXISTS word_frequencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                url TEXT NOT NULL,
                origin TEXT NOT NULL,
                depth INTEGER NOT NULL,
                frequency INTEGER NOT NULL DEFAULT 1,
                job_id INTEGER NOT NULL,
                FOREIGN KEY (job_id) REFERENCES crawl_jobs(id),
                UNIQUE(word, url, job_id)
            );

            CREATE INDEX IF NOT EXISTS idx_pages_job ON pages(job_id);
            CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
            CREATE INDEX IF NOT EXISTS idx_queue_status ON crawl_queue(status, job_id);
            CREATE INDEX IF NOT EXISTS idx_pages_content ON pages(content);
            CREATE INDEX IF NOT EXISTS idx_wf_word ON word_frequencies(word);
            CREATE INDEX IF NOT EXISTS idx_wf_url ON word_frequencies(url);
        """)
        await self.db.commit()

    # ── Crawl Jobs ──────────────────────────────────────────────

    async def create_job(self, origin: str, max_depth: int) -> int:
        now = time.time()
        cursor = await self.db.execute(
            "INSERT INTO crawl_jobs (origin, max_depth, status, created_at, updated_at) VALUES (?, ?, 'running', ?, ?)",
            (origin, max_depth, now, now),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def update_job_status(self, job_id: int, status: str):
        await self.db.execute(
            "UPDATE crawl_jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), job_id),
        )
        await self.db.commit()

    async def increment_job_counter(self, job_id: int, field: str):
        await self.db.execute(
            f"UPDATE crawl_jobs SET {field} = {field} + 1, updated_at = ? WHERE id = ?",
            (time.time(), job_id),
        )
        await self.db.commit()

    async def get_job(self, job_id: int) -> Optional[dict]:
        cursor = await self.db.execute("SELECT * FROM crawl_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_jobs(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM crawl_jobs ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_running_jobs(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM crawl_jobs WHERE status = 'running' ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Pages ───────────────────────────────────────────────────

    async def page_exists(self, url: str, job_id: int) -> bool:
        cursor = await self.db.execute(
            "SELECT 1 FROM pages WHERE url = ? AND job_id = ?", (url, job_id)
        )
        return await cursor.fetchone() is not None

    async def insert_page(self, url: str, job_id: int, origin: str, depth: int,
                          title: str = "", content: str = "", status: str = "indexed"):
        try:
            await self.db.execute(
                """INSERT OR IGNORE INTO pages (url, job_id, origin, depth, title, content, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (url, job_id, origin, depth, title, content, status, time.time()),
            )
            await self.db.commit()
        except Exception:
            pass  # duplicate — ignore

    async def get_indexed_page_count(self, job_id: Optional[int] = None) -> int:
        if job_id is not None:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM pages WHERE job_id = ? AND status = 'indexed'", (job_id,)
            )
        else:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM pages WHERE status = 'indexed'"
            )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_total_page_count(self) -> int:
        cursor = await self.db.execute("SELECT COUNT(*) FROM pages")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def search_pages(self, query: str) -> list[dict]:
        """Basic search — returns pages whose title or content contains query terms."""
        terms = query.lower().split()
        if not terms:
            return []

        # Build WHERE clause: each term must appear in title or content
        conditions = []
        params = []
        for term in terms:
            conditions.append("(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])

        where = " AND ".join(conditions)
        sql = f"""
            SELECT url, origin, depth, title, content, job_id
            FROM pages
            WHERE status = 'indexed' AND ({where})
            ORDER BY created_at DESC
        """
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Crawl Queue (for resumability) ──────────────────────────

    async def enqueue_url(self, url: str, job_id: int, depth: int) -> bool:
        """Add URL to crawl queue. Returns True if added, False if duplicate."""
        try:
            await self.db.execute(
                """INSERT OR IGNORE INTO crawl_queue (url, job_id, depth, status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (url, job_id, depth, time.time()),
            )
            await self.db.commit()
            return True
        except Exception:
            return False

    async def mark_queue_item(self, url: str, job_id: int, status: str):
        await self.db.execute(
            "UPDATE crawl_queue SET status = ? WHERE url = ? AND job_id = ?",
            (status, url, job_id),
        )
        await self.db.commit()

    async def get_pending_queue_items(self, job_id: int, limit: int = 100) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM crawl_queue WHERE job_id = ? AND status = 'pending' LIMIT ?",
            (job_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_queue_depth(self, job_id: Optional[int] = None) -> int:
        if job_id is not None:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM crawl_queue WHERE job_id = ? AND status = 'pending'",
                (job_id,),
            )
        else:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM crawl_queue WHERE status = 'pending'"
            )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def url_in_queue(self, url: str, job_id: int) -> bool:
        cursor = await self.db.execute(
            "SELECT 1 FROM crawl_queue WHERE url = ? AND job_id = ?", (url, job_id)
        )
        return await cursor.fetchone() is not None

    # ── Word Frequencies ────────────────────────────────────────

    async def insert_word_frequencies(self, word_freq_list: list[tuple]):
        """Bulk insert word frequencies. Each tuple: (word, url, origin, depth, frequency, job_id)"""
        await self.db.executemany(
            """INSERT OR REPLACE INTO word_frequencies (word, url, origin, depth, frequency, job_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            word_freq_list,
        )
        await self.db.commit()

    async def search_by_word(self, word: str, limit: int = 50) -> list[dict]:
        """Search word_frequencies table for exact word match."""
        cursor = await self.db.execute(
            """SELECT word, url, origin, depth, frequency
               FROM word_frequencies
               WHERE word = ?
               ORDER BY frequency DESC
               LIMIT ?""",
            (word.lower(), limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def export_to_pdata(self, filepath: str):
        """Export word_frequencies table to flat file (word url origin depth frequency)."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cursor = await self.db.execute(
            "SELECT word, url, origin, depth, frequency FROM word_frequencies ORDER BY word, url"
        )
        rows = await cursor.fetchall()
        with open(filepath, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(f"{row[0]} {row[1]} {row[2]} {row[3]} {row[4]}\n")

    # ── Cleanup ─────────────────────────────────────────────────

    async def close(self):
        if self.db:
            await self.db.close()
