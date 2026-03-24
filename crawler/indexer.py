"""
Async web crawler / indexer.
BFS crawl from an origin URL up to depth k.
Uses back pressure controls, deduplication, and persistent queue for resumability.
"""

import asyncio
import aiohttp
import logging
import os
import re
import time
from collections import Counter
from typing import Optional
from urllib.robotparser import RobotFileParser

from crawler.storage import Storage
from crawler.backpressure import BackPressureController
from crawler.utils import (
    normalize_url,
    extract_domain,
    extract_links,
    extract_text,
    extract_title,
    is_valid_crawl_url,
)

logger = logging.getLogger("crawler.indexer")

# Stop words to filter out of frequency counts
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "it", "its", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "our", "their", "what",
    "which", "who", "whom", "not", "no", "so", "if", "as", "from",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "up", "down", "then", "than",
}


def extract_word_frequencies(text: str) -> dict[str, int]:
    """Extract word frequencies from text, filtering stop words and short words."""
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    words = [w for w in words if w not in _STOP_WORDS and len(w) > 1]
    return dict(Counter(words))


class CrawlManager:
    """Manages one or more crawl jobs with shared back pressure controls."""

    def __init__(self, storage: Storage, backpressure: Optional[BackPressureController] = None):
        self.storage = storage
        self.bp = backpressure or BackPressureController()
        self._active_jobs: dict[int, asyncio.Task] = {}
        self._stop_signals: dict[int, asyncio.Event] = {}
        self._robot_cache: dict[str, Optional[RobotFileParser]] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=5, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": "WebCrawlerHW/1.0 (Educational Project)"},
            )
        return self._session

    async def start_job(self, origin: str, max_depth: int) -> int:
        """Start a new crawl job. Returns the job ID."""
        origin = normalize_url(origin)
        if not origin:
            raise ValueError("Invalid origin URL")

        job_id = await self.storage.create_job(origin, max_depth)
        stop_event = asyncio.Event()
        self._stop_signals[job_id] = stop_event

        task = asyncio.create_task(self._crawl_job(job_id, origin, max_depth, stop_event))
        self._active_jobs[job_id] = task

        # Clean up when done
        task.add_done_callback(lambda t: self._cleanup_job(job_id))
        logger.info(f"Started crawl job {job_id}: origin={origin}, depth={max_depth}")
        return job_id

    async def resume_jobs(self):
        """Resume any running jobs from before a restart."""
        running_jobs = await self.storage.get_running_jobs()
        for job in running_jobs:
            job_id = job["id"]
            if job_id not in self._active_jobs:
                logger.info(f"Resuming crawl job {job_id}: origin={job['origin']}")
                stop_event = asyncio.Event()
                self._stop_signals[job_id] = stop_event
                task = asyncio.create_task(
                    self._crawl_job(job_id, job["origin"], job["max_depth"], stop_event, resume=True)
                )
                self._active_jobs[job_id] = task
                task.add_done_callback(lambda t, jid=job_id: self._cleanup_job(jid))

    async def stop_job(self, job_id: int):
        """Signal a crawl job to stop."""
        if job_id in self._stop_signals:
            self._stop_signals[job_id].set()
            await self.storage.update_job_status(job_id, "stopped")
            logger.info(f"Stopped crawl job {job_id}")

    def _cleanup_job(self, job_id: int):
        self._active_jobs.pop(job_id, None)
        self._stop_signals.pop(job_id, None)

    async def _crawl_job(self, job_id: int, origin: str, max_depth: int,
                         stop_event: asyncio.Event, resume: bool = False):
        """Run the BFS crawl for a single job."""
        queue: asyncio.Queue = asyncio.Queue()
        seen: set[str] = set()

        if resume:
            # Reload pending URLs from database
            pending = await self.storage.get_pending_queue_items(job_id, limit=5000)
            for item in pending:
                url = item["url"]
                if url not in seen:
                    seen.add(url)
                    await queue.put((url, item["depth"]))
            logger.info(f"Job {job_id}: resumed with {queue.qsize()} pending URLs")
        else:
            # Start fresh
            seen.add(origin)
            await queue.put((origin, 0))
            await self.storage.enqueue_url(origin, job_id, 0)

        # Also mark already-crawled pages as seen
        if resume:
            from crawler.storage import Storage
            cursor = await self.storage.db.execute(
                "SELECT url FROM pages WHERE job_id = ? AND status = 'indexed'", (job_id,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                seen.add(row[0])

        workers = []
        num_workers = self.bp.concurrency.max_concurrent

        async def worker():
            session = await self._get_session()
            while not stop_event.is_set():
                try:
                    url, depth = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # No more URLs — check if other workers are still busy
                    if queue.empty():
                        break
                    continue

                try:
                    # Back pressure: acquire concurrency + rate limit
                    await self.bp.acquire()
                    try:
                        await self._process_url(
                            session, url, depth, max_depth, job_id, origin, queue, seen
                        )
                    finally:
                        await self.bp.release()
                except Exception as e:
                    logger.error(f"Job {job_id}: error processing {url}: {e}")
                    await self.storage.increment_job_counter(job_id, "pages_failed")
                    await self.storage.mark_queue_item(url, job_id, "failed")
                finally:
                    queue.task_done()

                # Update queue depth metric
                await self.bp.set_queue_depth(queue.qsize())

        # Launch workers
        for _ in range(num_workers):
            workers.append(asyncio.create_task(worker()))

        # Wait for all work to finish or stop signal
        try:
            done_task = asyncio.create_task(queue.join())
            stop_task = asyncio.create_task(stop_event.wait())
            done, pending = await asyncio.wait(
                [done_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        except Exception as e:
            logger.error(f"Job {job_id}: crawl error: {e}")

        # Cancel workers
        for w in workers:
            w.cancel()

        # Mark job complete
        if stop_event.is_set():
            await self.storage.update_job_status(job_id, "stopped")
        else:
            await self.storage.update_job_status(job_id, "completed")
            # Auto-export word frequencies to p.data
            pdata_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "storage", "p.data")
            await self.storage.export_to_pdata(pdata_path)
            logger.info(f"Job {job_id}: exported word frequencies to {pdata_path}")

        job = await self.storage.get_job(job_id)
        logger.info(
            f"Job {job_id} finished: {job['pages_crawled']} crawled, {job['pages_failed']} failed"
        )

    async def _process_url(self, session: aiohttp.ClientSession, url: str, depth: int,
                           max_depth: int, job_id: int, origin: str,
                           queue: asyncio.Queue, seen: set[str]):
        """Fetch a URL, extract content and links, store results."""
        # Check robots.txt
        if not await self._check_robots(session, url):
            await self.storage.mark_queue_item(url, job_id, "blocked")
            return

        try:
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                if response.status != 200:
                    await self.storage.mark_queue_item(url, job_id, "failed")
                    await self.storage.increment_job_counter(job_id, "pages_failed")
                    return

                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type.lower():
                    await self.storage.mark_queue_item(url, job_id, "skipped")
                    return

                html = await response.text(errors="replace")
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            await self.storage.mark_queue_item(url, job_id, "failed")
            await self.storage.increment_job_counter(job_id, "pages_failed")
            return

        # Extract content
        title = extract_title(html)
        text = extract_text(html)

        # Store the page
        await self.storage.insert_page(
            url=url, job_id=job_id, origin=origin,
            depth=depth, title=title, content=text[:50000],  # Cap content size
            status="indexed",
        )
        await self.storage.increment_job_counter(job_id, "pages_crawled")
        await self.storage.mark_queue_item(url, job_id, "done")

        # Extract and store word frequencies
        full_text = f"{title} {text}"
        word_freqs = extract_word_frequencies(full_text)
        if word_freqs:
            freq_tuples = [
                (word, url, origin, depth, freq, job_id)
                for word, freq in word_freqs.items()
            ]
            await self.storage.insert_word_frequencies(freq_tuples)

        # Discover links if not at max depth
        if depth < max_depth:
            links = extract_links(html, url)
            for link in links:
                if link not in seen and is_valid_crawl_url(link):
                    if not self.bp.can_enqueue():
                        break  # Queue depth limit reached
                    seen.add(link)
                    await self.storage.enqueue_url(link, job_id, depth + 1)
                    await queue.put((link, depth + 1))

    async def _check_robots(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Check if crawling this URL is allowed by robots.txt."""
        domain = extract_domain(url)
        if domain in self._robot_cache:
            rp = self._robot_cache[domain]
            if rp is None:
                return True  # Could not fetch robots.txt — allow
            return rp.can_fetch("WebCrawlerHW/1.0", url)

        # Fetch robots.txt
        from urllib.parse import urlparse
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with session.get(robots_url, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="replace")
                    rp = RobotFileParser()
                    rp.parse(text.splitlines())
                    self._robot_cache[domain] = rp
                    return rp.can_fetch("WebCrawlerHW/1.0", url)
                else:
                    self._robot_cache[domain] = None
                    return True
        except Exception:
            self._robot_cache[domain] = None
            return True

    async def get_status(self) -> dict:
        """Get overall system status."""
        jobs = await self.storage.get_all_jobs()
        total_pages = await self.storage.get_total_page_count()
        total_queue = await self.storage.get_queue_depth()

        bp_metrics = self.bp.get_metrics()
        bp_metrics.queue_depth = total_queue

        return {
            "jobs": jobs,
            "total_pages_indexed": total_pages,
            "total_queue_depth": total_queue,
            "active_job_count": len(self._active_jobs),
            "backpressure": bp_metrics.to_dict(),
        }

    async def close(self):
        # Stop all active jobs
        for job_id in list(self._stop_signals.keys()):
            self._stop_signals[job_id].set()

        # Wait for tasks
        if self._active_jobs:
            await asyncio.gather(*self._active_jobs.values(), return_exceptions=True)

        if self._session and not self._session.closed:
            await self._session.close()
