# Web Crawler

A scalable web crawler with indexing, TF-IDF search, back pressure controls, and a real-time dashboard. Built with Python, asyncio, and SQLite.

## Quick Start

### Prerequisites
- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/mucahit-gunay/blg483HW1

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
python server.py
```

Open **http://localhost:3600** in your browser.

## How It Works

### Indexing
1. Enter a URL and select a crawl depth (0–5) in the dashboard
2. Click **Start Crawl** — the crawler begins a BFS traversal from the origin URL
3. At each depth level, it fetches pages, extracts text content, and discovers new links
4. The crawl respects `robots.txt`, deduplicates URLs, and applies back pressure controls

### Searching
1. Enter search terms in the search panel
2. The system uses TF-IDF relevance scoring to rank indexed pages
3. Results are returned as `(relevant_url, origin_url, depth)` triples
4. Search works while indexing is active — new pages appear in results immediately

### System Monitoring
The dashboard shows real-time metrics:
- **Pages Indexed**: total number of crawled and stored pages
- **Queue Depth**: URLs waiting to be crawled
- **Active Workers**: concurrent fetch operations (max 10)
- **Requests/sec**: current crawl throughput
- **Back Pressure**: visual indicator of system load

### Resumability
The crawl state (jobs, pages, queue) is stored in SQLite. If the server is stopped and restarted, in-progress jobs automatically resume from where they left off.

## Project Structure

```
├── crawler/
│   ├── __init__.py          # Package init
│   ├── storage.py           # SQLite storage layer
│   ├── backpressure.py      # Concurrency, rate limiting, queue depth controls
│   ├── indexer.py           # Async BFS web crawler
│   ├── utils.py             # URL normalization, text extraction
│   └── searcher.py          # TF-IDF search engine
├── static/
│   ├── index.html           # Dashboard UI
│   ├── style.css            # Styling
│   └── app.js               # Frontend logic
├── server.py                # FastAPI server
├── requirements.txt         # Python dependencies
├── product_prd.md           # Product requirements document
├── recommendation.md        # Production deployment recommendations
└── readme.md                # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/index` | POST | Start a crawl job `{"url": "...", "depth": 2}` |
| `/search` | GET | Search with relevance scoring `?query=...&sortBy=relevance` |
| `/api/export` | POST | Export word frequencies to `data/storage/p.data` |
