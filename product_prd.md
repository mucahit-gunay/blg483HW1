# Web Crawler — Product Requirements Document

## Overview

A web crawler system that provides two core capabilities:

1. **Index**: Crawl web pages starting from a given URL up to a configurable depth
2. **Search**: Find indexed pages relevant to a text query

The system runs on localhost and provides a web-based dashboard for controlling and monitoring operations.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Web UI (Dashboard)             │
│          index.html / style.css / app.js        │
└─────────────────┬───────────────────────────────┘
                  │ HTTP / REST
┌─────────────────▼───────────────────────────────┐
│              FastAPI Server (server.py)          │
│   /api/index  /api/search  /api/status  /api/jobs│
└───┬──────────────┬──────────────────────────────┘
    │              │
┌───▼──────┐  ┌────▼─────┐  ┌──────────────────┐
│ Indexer  │  │ Searcher │  │  BackPressure     │
│(BFS Crawl│  │ (TF-IDF) │  │  Controller       │
│ asyncio) │  │          │  │  (Semaphore +     │
│          │  │          │  │   Rate Limiter +  │
│          │  │          │  │   Queue Depth)    │
└───┬──────┘  └────┬─────┘  └──────────────────┘
    │              │
┌───▼──────────────▼──────────────────────────────┐
│            SQLite Storage (WAL mode)            │
│    crawl_jobs | pages | crawl_queue             │
└─────────────────────────────────────────────────┘
```

## Core Features

### Index (Crawl)
- Accept a URL (`origin`) and depth (`k`) parameter
- BFS traversal up to `k` hops from origin
- Never crawl the same page twice (URL deduplication)
- Respect `robots.txt`
- Back pressure: configurable concurrency limit (10 workers), rate limit (20 req/s), queue depth cap (10,000)
- Store page title and text content for search

### Search
- Accept a query string, return `(relevant_url, origin_url, depth)` triples
- Hand-rolled TF-IDF relevance scoring with title boosting
- Live results — queries the database directly, so new pages appear immediately even during active crawls

### Dashboard UI
- Start/stop crawl jobs
- Search indexed content
- Real-time metrics: pages indexed, queue depth, active workers, requests/sec, back pressure status
- Job progress tracking with progress bars

### Resumability
- Crawl state persisted to SQLite (WAL mode)
- Unfinished jobs automatically resume on server restart
- Crawl queue stored in DB — no data loss on interruption

## Technology Stack
| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Async HTTP | aiohttp |
| HTML Parsing | BeautifulSoup4 (parsing only) |
| Database | SQLite (aiosqlite, WAL mode) |
| API Server | FastAPI + uvicorn |
| Search | Hand-rolled TF-IDF |
| Frontend | Vanilla HTML/CSS/JS |

## Design Decisions

1. **Language-native**: Core crawling logic, BFS, deduplication, and TF-IDF search are all hand-written using Python standard library and asyncio. No full-featured crawler or search engine libraries.

2. **Single-machine scale**: SQLite with WAL mode provides concurrent reads during writes. asyncio provides efficient I/O without threads. The system can handle thousands of pages on a single machine.

3. **Back pressure**: Three-layered approach (concurrency semaphore + token-bucket rate limiter + queue depth cap) ensures controlled resource usage.

4. **Real-time search**: Search queries the database directly, not an in-memory index, so results reflect the latest crawled pages at any moment.
