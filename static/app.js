/**
 * Web Crawler Dashboard — Frontend Logic
 * Handles form submissions, polling for status, and rendering results.
 */

const API = '';  // same origin

// ── DOM References ────────────────────────────────────
const indexForm = document.getElementById('indexForm');
const searchForm = document.getElementById('searchForm');
const depthSlider = document.getElementById('depth');
const depthValue = document.getElementById('depthValue');
const indexBtn = document.getElementById('indexBtn');
const searchBtn = document.getElementById('searchBtn');
const systemStatus = document.getElementById('systemStatus');

const pagesIndexed = document.getElementById('pagesIndexed');
const queueDepth = document.getElementById('queueDepth');
const activeWorkers = document.getElementById('activeWorkers');
const maxWorkers = document.getElementById('maxWorkers');
const rps = document.getElementById('rps');
const totalRequests = document.getElementById('totalRequests');
const throttleEvents = document.getElementById('throttleEvents');
const bpFill = document.getElementById('bpFill');
const bpStatus = document.getElementById('bpStatus');

const jobsList = document.getElementById('jobsList');
const resultsCard = document.getElementById('resultsCard');
const resultCount = document.getElementById('resultCount');
const searchResults = document.getElementById('searchResults');

// ── Depth Slider ──────────────────────────────────────
depthSlider.addEventListener('input', () => {
    depthValue.textContent = depthSlider.value;
});

// ── Toast ─────────────────────────────────────────────
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = '0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Index Form ────────────────────────────────────────
indexForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = document.getElementById('url').value.trim();
    const depth = parseInt(depthSlider.value);

    if (!url) return;

    indexBtn.disabled = true;
    indexBtn.innerHTML = '<span class="spinner"></span> Starting...';

    try {
        const res = await fetch(`${API}/api/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, depth }),
        });
        const data = await res.json();

        if (res.ok) {
            showToast(`Crawl job #${data.job_id} started!`);
            document.getElementById('url').value = '';
            refreshJobs();
        } else {
            showToast(data.detail || 'Failed to start crawl', 'error');
        }
    } catch (err) {
        showToast('Connection error', 'error');
    } finally {
        indexBtn.disabled = false;
        indexBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Start Crawl`;
    }
});

// ── Search Form ───────────────────────────────────────
searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = document.getElementById('query').value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> Searching...';

    try {
        const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        resultsCard.style.display = 'block';
        resultCount.textContent = `${data.count} result${data.count !== 1 ? 's' : ''}`;

        if (data.results.length === 0) {
            searchResults.innerHTML = '<p class="empty-state">No results found.</p>';
        } else {
            searchResults.innerHTML = data.results.map(r => `
                <div class="result-item">
                    <div class="result-title">${escapeHtml(r.title || 'Untitled')}</div>
                    <a href="${escapeHtml(r.relevant_url)}" class="result-url" target="_blank">${escapeHtml(r.relevant_url)}</a>
                    <div class="result-meta">
                        <span>Origin: <strong>${escapeHtml(r.origin_url)}</strong></span>
                        <span>Depth: <strong>${r.depth}</strong></span>
                        <span>Score: <strong>${r.score}</strong></span>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        showToast('Search failed', 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            Search`;
    }
});

// ── Stop Job ──────────────────────────────────────────
async function stopJob(jobId) {
    try {
        await fetch(`${API}/api/jobs/${jobId}/stop`, { method: 'POST' });
        showToast(`Job #${jobId} stopped`);
        refreshJobs();
    } catch {
        showToast('Failed to stop job', 'error');
    }
}

// ── Refresh Jobs ──────────────────────────────────────
async function refreshJobs() {
    try {
        const res = await fetch(`${API}/api/jobs`);
        const data = await res.json();
        renderJobs(data.jobs);
    } catch {
        // silent
    }
}

function renderJobs(jobs) {
    if (!jobs || jobs.length === 0) {
        jobsList.innerHTML = '<p class="empty-state">No crawl jobs yet. Start one above!</p>';
        return;
    }

    jobsList.innerHTML = jobs.map(job => {
        const total = (job.pages_crawled || 0) + (job.queue_depth || 0);
        const pct = total > 0 ? Math.round(((job.pages_crawled || 0) / total) * 100) : 0;

        return `
            <div class="job-item">
                <div class="job-header">
                    <span class="job-origin" title="${escapeHtml(job.origin)}">${escapeHtml(job.origin)}</span>
                    <span class="job-badge ${job.status}">${job.status}</span>
                </div>
                <div class="job-stats">
                    <span>Pages: <strong>${job.pages_crawled || 0}</strong></span>
                    <span>Failed: <strong>${job.pages_failed || 0}</strong></span>
                    <span>Queue: <strong>${job.queue_depth || 0}</strong></span>
                    <span>Depth: <strong>${job.max_depth}</strong></span>
                </div>
                <div class="job-progress">
                    <div class="job-progress-fill" style="width: ${pct}%"></div>
                </div>
                ${job.status === 'running' ? `
                    <div class="job-actions">
                        <button class="btn btn-danger" onclick="stopJob(${job.id})">Stop</button>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// ── Refresh Status ────────────────────────────────────
async function refreshStatus() {
    try {
        const res = await fetch(`${API}/api/status`);
        const data = await res.json();
        const bp = data.backpressure || {};

        // Update metrics
        pagesIndexed.textContent = data.total_pages_indexed || 0;
        queueDepth.textContent = data.total_queue_depth || 0;
        activeWorkers.textContent = bp.active_workers || 0;
        maxWorkers.textContent = `/${bp.max_workers || 10}`;
        rps.textContent = bp.requests_per_second || 0;
        totalRequests.textContent = bp.total_requests || 0;
        throttleEvents.textContent = bp.total_throttle_events || 0;

        // Back pressure bar
        const workers = bp.active_workers || 0;
        const maxW = bp.max_workers || 10;
        const qd = data.total_queue_depth || 0;
        const maxQd = bp.max_queue_depth || 10000;
        const pressure = Math.max(
            (workers / maxW) * 100,
            (qd / maxQd) * 100
        );
        bpFill.style.width = `${Math.min(pressure, 100)}%`;

        if (bp.is_throttled) {
            bpStatus.textContent = 'Throttled';
            bpStatus.className = 'bp-status critical';
        } else if (pressure > 60) {
            bpStatus.textContent = 'High';
            bpStatus.className = 'bp-status warning';
        } else {
            bpStatus.textContent = 'Normal';
            bpStatus.className = 'bp-status';
        }

        // System status pill
        if (data.active_job_count > 0) {
            systemStatus.classList.add('active');
            systemStatus.querySelector('.status-text').textContent = `Crawling (${data.active_job_count} job${data.active_job_count > 1 ? 's' : ''})`;
        } else {
            systemStatus.classList.remove('active');
            systemStatus.querySelector('.status-text').textContent = 'Idle';
        }

        // Also refresh jobs
        renderJobs(data.jobs);
    } catch {
        // silent
    }
}

// ── Helpers ───────────────────────────────────────────
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Init ──────────────────────────────────────────────
refreshStatus();
refreshJobs();
setInterval(refreshStatus, 2000);
