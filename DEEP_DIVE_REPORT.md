# Deep Dive Report — Technical Documentation

> **Document Version**: 1.0  
> **Last Updated**: 2026-05-03  
> **Author**: Kimi Code (AI Agent)  
> **Project**: GDELT Analysis Platform (Virginia Tech)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Technology Stack](#3-technology-stack)
4. [Backend Components](#4-backend-components)
5. [Frontend Components](#5-frontend-components)
6. [API Endpoints](#6-api-endpoints)
7. [Data Models](#7-data-models)
8. [GKG BigQuery Integration](#8-gkg-bigquery-integration)
9. [Configuration & Environment Variables](#9-configuration--environment-variables)
10. [Known Issues & Fixes](#10-known-issues--fixes)
11. [Future Enhancements](#11-future-enhancements)

---

## 1. Overview

**Deep Dive Report** (internally called "Enhanced Event Report" or "Reporter v2") is a comprehensive event analysis feature that goes beyond the basic AI summary. It enriches event data with:

- **Storyline**: Timeline visualization, entity evolution tracking, theme evolution
- **News Coverage**: Live article fetching from event SOURCEURLs + ChromaDB fallback
- **GKG Insights**: Media Knowledge Graph data from GDELT's BigQuery dataset (entities, themes, tone trends)

Users trigger it from the AI Explore panel by clicking **"Deep Dive Report"** after receiving initial query results.

---

## 2. Architecture & Data Flow

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Frontend                                   │
│  ExplorePanel.tsx ──► clicks "Deep Dive Report"                             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ POST /api/v1/analyze/event-report
                                │ { data: <analyze_results>, prompt, flags }
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                                      │
│                                                                              │
│  analyze.py /event-report                                                    │
│       │                                                                      │
│       ▼                                                                      │
│  EnhancedReportGenerator.generate_event_report()                             │
│       │                                                                      │
│       ├──► _gather_news_coverage() ──► NewsScraper.fetch_for_event()        │
│       │              ├──► HTTP fetch SOURCEURL (aiohttp + BeautifulSoup)    │
│       │              └──► ChromaDB fallback (if URL fails)                   │
│       │                                                                      │
│       ├──► _gather_related_news() ──► NewsScraper.fetch_for_events()        │
│       │                                                                      │
│       ├──► _gather_gkg_data() ──► GKGClient (BigQuery)                      │
│       │              ├──► get_cooccurring_entities()                         │
│       │              ├──► get_entity_themes()                                │
│       │              └──► get_tone_timeline()                                │
│       │                                                                      │
│       ├──► _extract_events_for_storyline()                                  │
│       │              └──► build_full_storyline()                             │
│       │                      ├──► build_timeline()                           │
│       │                      ├──► build_entity_evolution()                   │
│       │                      ├──► build_theme_evolution()                    │
│       │                      └──► build_narrative_arc()                      │
│       │                                                                      │
│       └──► LLM (LangChain) ──► generate narrative report                   │
│                                                                              │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ JSON response
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend Render                                    │
│  EventReportPanel.tsx                                                        │
│       ├──► Summary + Key Findings                                            │
│       ├──► StorylineTimeline.tsx (timeline / entities / themes tabs)        │
│       ├──► NewsCoveragePanel.tsx (source list with status)                   │
│       └──► GKGInsightCards.tsx (people, orgs, themes, tone chart)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Parallel Data Gathering

Inside `generate_event_report()`, three data sources are fetched concurrently via `asyncio.gather()`:

```python
news_coverage, related_news, gkg_data = await asyncio.gather(
    self._gather_news_coverage(data),   # ~1-5s (HTTP dependent)
    self._gather_related_news(data),    # ~1-5s
    self._gather_gkg_data(data),        # ~2-10s (BigQuery dependent)
)
```

Storyline building happens **after** GKG data returns (because theme evolution needs GKG themes).

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend Framework** | Python 3.13, FastAPI, Uvicorn | API server |
| **LLM Framework** | LangChain, LangChain-OpenAI | Report generation |
| **HTTP Client** | aiohttp | Async news article fetching |
| **HTML Parsing** | BeautifulSoup4 | Article content extraction |
| **Vector DB** | ChromaDB | News content fallback / RAG |
| **BigQuery** | google-cloud-bigquery | GKG data queries |
| **Auth** | google-oauth2 (service account) | GCP authentication |
| **Frontend** | React 18, TypeScript, Vite | UI rendering |
| **Icons** | Lucide React | UI icons |

### 3.1 Python Dependencies

```txt
# Core
fastapi>=0.115.0
uvicorn[standard]
pydantic>=2.9.0

# LLM
langchain>=0.3.0
langchain-openai>=0.2.0
openai>=1.55.0

# HTTP / Scraping
aiohttp>=3.9.0
beautifulsoup4>=4.12.0

# BigQuery (optional — only needed for GKG)
google-cloud-bigquery>=3.0.0
google-auth>=2.0.0

# Vector DB
chromadb>=0.5.0
```

---

## 4. Backend Components

### 4.1 Enhanced Reporter (`backend/agents/enhanced_reporter.py`)

**Class**: `EnhancedReportGenerator` extends `ReportGenerator`

**Key Methods**:

| Method | Purpose | Async |
|--------|---------|-------|
| `generate_event_report()` | Main orchestrator — gathers data, builds storyline, calls LLM | ✅ |
| `_gather_news_coverage()` | Fetch primary event's news article | ✅ |
| `_gather_related_news()` | Fetch news for related events | ✅ |
| `_gather_gkg_data()` | Query BigQuery for GKG insights | ✅ |
| `_extract_events_for_storyline()` | Flatten step results into event list | ❌ |
| `_format_enhanced_data()` | Build LLM prompt from all sources | ❌ |
| `_parse_report_text()` | Parse LLM output into summary + findings | ❌ |

**Singleton Access**:
```python
from backend.agents.enhanced_reporter import get_enhanced_reporter
reporter = get_enhanced_reporter(config)
```

### 4.2 Storyline Builder (`backend/services/storyline_builder.py`)

Pure functions — no external dependencies.

| Function | Input | Output |
|----------|-------|--------|
| `build_full_storyline(events, gkg_data)` | Event list + optional GKG themes | `dict` with 4 keys |
| `build_timeline(events)` | Event list | Timeline with milestones |
| `build_entity_evolution(events)` | Event list | Actor/location tracking |
| `build_theme_evolution(gkg_themes)` | GKG parsed themes | Theme trends |
| `build_narrative_arc(...)` | Timeline + entities + themes | Text summary for LLM |

**Significance Score Calculation** (0-10):
- Articles coverage: max 4 pts (`articles / 50`)
- Goldstein intensity: max 3 pts (`|goldstein| / 2`)
- Fingerprint severity score: raw value
- Has headline + summary: +1 pt

### 4.3 News Scraper (`backend/services/news_scraper.py`)

**Class**: `NewsScraper`

**Features**:
- In-memory URL cache (TTL 1 hour)
- Max 5 concurrent fetches (semaphore)
- Timeout: 12s total, 5s connect
- Content limits: 150 chars min, 8000 chars max, 5MB max download
- Smart extraction: `article` → `main` → `role='main'` → all `<p>` tags with class scoring
- ChromaDB fallback when URL fetch fails

**Fetch Status Values**:
| Status | Meaning |
|--------|---------|
| `success` | Article fetched and extracted |
| `cached_success` | Returned from cache |
| `chroma_fallback` | URL failed, used ChromaDB |
| `http_xxx` | HTTP error (e.g., 404, 403) |
| `timeout` | Request timed out |
| `too_large` | Content exceeded 5MB |
| `too_short` | Extracted text < 150 chars |

### 4.4 GKG Client (`backend/services/gkg_client.py`)

**Class**: `GKGClient`

**Cost Protection**:
- Mandatory `_PARTITIONTIME` filter (queries rejected without it)
- Dry-run before execution to estimate bytes
- Per-query limit: 1GB default
- Daily quota: 10GB default (~$0.05/day)
- In-memory result cache (TTL 1 hour)

**Query Methods**:

| Method | BigQuery Table | Cost Control |
|--------|---------------|--------------|
| `get_event_gkg_records(date)` | `gdelt-bq.gdeltv2.gkg_partitioned` | 500MB limit, single day |
| `get_entity_themes(entity, date_range)` | Same | 1GB limit, max 7 days |
| `get_cooccurring_entities(entity, date)` | Same | 500MB limit, single day |
| `get_tone_timeline(entity, date_range)` | Same | 1GB limit, max 14 days |

**GKG Data Parsers**:
- `_parse_gkg_themes()`: Parses `V2Themes` (format: `THEME,score;THEME,score;...`)
- `_parse_cooccurring_entities()`: Parses `V2Persons` and `V2Orgs` (semicolon-delimited)

---

## 5. Frontend Components

### 5.1 ExplorePanel (`frontend/src/components/ExplorePanel.tsx`)

Renders the **"Quick Report"** and **"Deep Dive Report"** buttons after AI analysis completes:

```tsx
// Buttons appear when:
// - visualization includes 'report'
// - report_prompt exists
// - no report is currently loading or displayed
{vizes.includes('report') && result?.plan?.report_prompt && !report && !reportLoading && !enhancedReport && !enhancedReportLoading && (
  <div style={{ display: 'flex', gap: 10 }}>
    <button onClick={() => loadReport(result.data, result.plan.report_prompt!)}>
      <FileText size={14} /> Quick Report
    </button>
    <button onClick={() => loadEnhancedReport(result.data, result.plan.report_prompt!)}>
      <BookOpen size={14} /> Deep Dive Report
    </button>
  </div>
)}
```

### 5.2 EventReportPanel (`frontend/src/components/EventReportPanel.tsx`)

Main container for Deep Dive Report output. Displays:
- Report header with generation timestamp
- AI-generated summary (paragraphs)
- Key findings (bullet list)
- Data source badges (Storyline | News Coverage | GKG Insights)

### 5.3 StorylineTimeline (`frontend/src/components/StorylineTimeline.tsx`)

Three-tab component:

| Tab | Content |
|-----|---------|
| **Timeline** | Chronological event nodes with significance scoring, expandable details (Goldstein, Articles, Tone) |
| **Entities** | Actor cards (name, event count, role, Goldstein avg) + Location cards |
| **Themes** | Dominant theme tags, emerging themes (green), declining themes (red) |

### 5.4 NewsCoveragePanel (`frontend/src/components/NewsCoveragePanel.tsx`)

- Source count badge
- Headline display
- Source list with status icons:
  - ✅ Fetched (green)
  - 🗄️ From KB (blue — ChromaDB fallback)
  - ⚠️ Error variants (red)
- External link to original source

### 5.5 GKGInsightCards (`frontend/src/components/GKGInsightCards.tsx`)

- **Related People**: Purple tag pills with mention counts
- **Related Organizations**: Gray tag pills
- **Media Themes**: Green tag pills
- **Tone Trend**: Mini bar chart (red = negative, green = positive)

When GKG is unavailable, shows a configuration hint:
> "GKG BigQuery data not available. Configure GCP credentials to enable media knowledge graph insights."

---

## 6. API Endpoints

### 6.1 POST `/api/v1/analyze/event-report`

**Request Body** (`EventReportRequest`):

```json
{
  "data": {
    "event_detail_0": { "type": "event_detail", "data": { ... } },
    "similar_events_1": { "type": "similar_events", "data": [ ... ] }
  },
  "prompt": "Optional custom prompt",
  "include_storyline": true,
  "include_news": true,
  "include_gkg": true,
  "llm_config": { "provider": "kimi", "api_key": "...", "model": "..." }
}
```

**Response** (`EventReportResponse`):

```json
{
  "ok": true,
  "report": {
    "summary": "AI-generated narrative...",
    "key_findings": ["Finding 1", "Finding 2"],
    "storyline": {
      "timeline": { "events": [...], "period": {...}, "key_milestones": [...] },
      "entity_evolution": { "actors": [...], "locations": [...] },
      "theme_evolution": { "dominant_themes": [...], "emerging_themes": [...] },
      "narrative_arc": "Story Period: ...\nTotal Events: ..."
    },
    "news_coverage": {
      "headline": "...",
      "sources": [{ "url": "...", "title": "...", "fetch_status": "success" }],
      "primary_content": "...",
      "has_content": true
    },
    "gkg_insights": {
      "cooccurring": { "top_persons": [...], "top_organizations": [...] },
      "themes": { "top_themes": [...] },
      "tone_timeline": [{ "date": "...", "avg_tone": -2.5, "mention_count": 10 }]
    },
    "generated_at": "2026-05-03T01:28:30.090347"
  },
  "elapsed_ms": 23531.8
}
```

### 6.2 POST `/api/v1/analyze/storyline`

Standalone endpoint for storyline data without LLM report generation.

**Request**:
```json
{ "fingerprint": "US-20240226-WAS-PROTEST-330", "event_id": 1160074330 }
```

**Response**:
```json
{
  "ok": true,
  "storyline": { "timeline": {...}, "entity_evolution": {...}, "theme_evolution": {...}, "narrative_arc": "..." },
  "elapsed_ms": 450.2
}
```

---

## 7. Data Models

### 7.1 Backend (Pydantic)

Defined in `backend/schemas/responses.py`:

| Model | Key Fields |
|-------|-----------|
| `EventReportRequest` | `data`, `prompt`, `include_storyline`, `include_news`, `include_gkg` |
| `EventReportResponse` | `ok`, `error`, `report: EnhancedReportOutput`, `elapsed_ms` |
| `EnhancedReportOutput` | `summary`, `key_findings`, `storyline`, `news_coverage`, `gkg_insights`, `generated_at` |
| `StorylineData` | `timeline`, `entity_evolution`, `theme_evolution`, `narrative_arc` |
| `NewsCoverageData` | `headline`, `sources: List[NewsSourceItem]`, `primary_content`, `has_content` |
| `GKGInsightData` | `cooccurring`, `themes`, `tone_timeline` |

### 7.2 Frontend (TypeScript)

Defined in `frontend/src/types/index.ts`:

| Interface | Key Fields |
|-----------|-----------|
| `EnhancedReportResult` | `summary`, `key_findings`, `storyline?`, `news_coverage?`, `gkg_insights?`, `generated_at` |
| `StorylineData` | `timeline`, `entity_evolution`, `theme_evolution`, `narrative_arc` |
| `NewsCoverageData` | `headline?`, `sources`, `primary_content`, `has_content` |
| `GKGInsightData` | `cooccurring?`, `themes?`, `tone_timeline` |
| `TimelineEventItem` | `date`, `title`, `description`, `actors`, `significance_score`, `goldstein_scale`, `num_articles` |

---

## 8. GKG BigQuery Integration

### 8.1 What is GKG?

**GDELT Global Knowledge Graph (GKG)** is a separate dataset from the GDELT Events database. It contains:
- **Persons** mentioned in news (`V2Persons`)
- **Organizations** (`V2Orgs`)
- **Themes** (`V2Themes`) — e.g., "PROTEST", "ECON_INFLATION", "WB_1234_GENDER"
- **Tone** (`V2Tone`) — sentiment scores
- **Locations** (`V2Locations`)

GKG is hosted on **Google BigQuery** as a public dataset: `gdelt-bq.gdeltv2.gkg_partitioned`.

### 8.2 Why GCP Credentials Are Required

The GKG dataset is **public** (free to query), but Google Cloud Platform requires authentication to access BigQuery:

1. **Service Account** (recommended for production):
   - Create a GCP project
   - Enable BigQuery API
   - Create a service account with `BigQuery Data Viewer` + `BigQuery Job User` roles
   - Download JSON key file
   - Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

2. **Application Default Credentials** (for local dev):
   - Run `gcloud auth application-default login`
   - No key file needed, uses your personal Google account

### 8.3 Cost Structure

| Item | Value |
|------|-------|
| GKG dataset cost | **Free** (GDELT hosts it publicly) |
| BigQuery on-demand pricing | $5 per TB scanned |
| Our daily limit | 10 GB (~$0.05/day) |
| Per-query limit | 1 GB |
| Without partition filter | ~3.6 TB per query (~$18) ⚠️ |

**Critical**: The code enforces `_PARTITIONTIME` filtering. A query without it scans the entire dataset and would cost ~$18.

### 8.4 Setup Instructions

#### Step 1: Create GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., `gdelt-analysis`)
3. Enable billing (required even for free-tier queries)
4. Enable the **BigQuery API**

#### Step 2: Create Service Account

```bash
# Via gcloud CLI
gcloud iam service-accounts create gdelt-gkg-reader \
  --display-name="GDELT GKG Reader"

# Grant roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:gdelt-gkg-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:gdelt-gkg-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Download key
gcloud iam service-accounts keys create gkg-service-account.json \
  --iam-account=gdelt-gkg-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

#### Step 3: Configure Environment

Add to `.env`:

```bash
# GKG BigQuery Configuration
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gkg-service-account.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DAILY_GB_LIMIT=10
BIGQUERY_QUERY_TIMEOUT_SEC=30
GKG_CACHE_TTL_SEC=3600
```

For Docker, mount the secrets directory:

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - .:/app
      - ./secrets:/app/secrets:ro
```

#### Step 4: Verify

```bash
# Test GKG client directly
curl -X POST http://localhost:8000/api/v1/analyze/event-report \
  -H "Content-Type: application/json" \
  -d '{
    "data": {"event_detail_0": {"type": "event_detail", "data": {"fingerprint": "US-20240226-WAS-PROTEST-330", "headline": "Test", "event_data": {"GlobalEventID": 1160074330, "SQLDATE": "2024-02-26", "Actor1Name": "ISRAELI"}}}},
    "include_gkg": true
  }'
```

Check backend logs for:
```
[GKGClient] BigQuery client initialized (project=your-gcp-project-id)
[GKGClient] Query OK: 15 rows, 45.23MB processed, $0.0002
```

### 8.5 Without GCP (Graceful Degradation)

If GKG is not configured, the system works fine — just without GKG insights:

- `gkg_client.available` returns `false`
- `_gather_gkg_data()` returns `None`
- `theme_evolution` returns empty arrays
- Frontend shows: "GKG BigQuery data not available. Configure GCP credentials..."

---

## 9. Configuration & Environment Variables

### 9.1 Required for Deep Dive

| Variable | Required | Description |
|----------|----------|-------------|
| `KIMI_CODE_API_KEY` | ✅ | LLM API key (or `OPENAI_API_KEY`, `MOONSHOT_API_KEY`) |
| `LLM_PROVIDER` | ❌ | `kimi` (default), `openai`, `moonshot`, `claude` |
| `LLM_MODEL` | ❌ | e.g., `kimi-k2-0905-preview` |

### 9.2 Optional (GKG only)

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to GCP service account JSON |
| `BIGQUERY_PROJECT_ID` | — | GCP project ID |
| `BIGQUERY_DAILY_GB_LIMIT` | 10 | Daily query budget in GB |
| `BIGQUERY_QUERY_TIMEOUT_SEC` | 30 | Query timeout |
| `GKG_CACHE_TTL_SEC` | 3600 | Result cache TTL |

---

## 10. Known Issues & Fixes

### 10.1 Bug: `dict` object has no attribute `narrative_arc`

**Status**: ✅ Fixed (2026-05-03)

**Root Cause**: `build_full_storyline()` returns a plain `dict`, but `enhanced_reporter.py` treated it as an object with `.to_dict()` and `.narrative_arc` attributes.

**Fix**: Changed all storyline access to be dict-compatible:

```python
# Before (broken):
storyline.to_dict() if storyline else None
storyline.narrative_arc
storyline.timeline

# After (fixed):
storyline if isinstance(storyline, dict) else (storyline.to_dict() if storyline else None)
storyline.get("narrative_arc") if isinstance(storyline, dict) else storyline.narrative_arc
storyline.get("timeline") if isinstance(storyline, dict) else storyline.timeline
```

**Files Modified**: `backend/agents/enhanced_reporter.py`

### 10.2 Docker Code Sync

**Issue**: Code edits on host don't reflect in running container immediately.

**Solution**: Restart container after backend code changes:
```bash
docker restart gdelt_backend
```

### 10.3 News Fetch Reliability

**Issue**: Many SOURCEURLs return 403/404 or block scrapers.

**Mitigation**:
- ChromaDB fallback for failed fetches
- In-memory cache reduces repeated failures
- Frontend shows fetch status per source

---

## 11. Future Enhancements

| Feature | Description | Priority |
|---------|-------------|----------|
| **GKG caching to MySQL** | Persist GKG results to avoid re-querying BigQuery | Medium |
| **Batch news fetching** | Pre-fetch articles for top events in background | Medium |
| **Storyline export** | Download storyline as PDF/JSON | Low |
| **Multi-language support** | Translate reports to user's language | Low |
| **GKG sentiment sparkline** | Better tone visualization over time | Low |
| **Event comparison** | Compare two events side-by-side in Deep Dive | Low |

---

## Appendix: File Reference

### Backend

| File | Lines | Purpose |
|------|-------|---------|
| `backend/agents/enhanced_reporter.py` | 474 | Main report generator |
| `backend/services/storyline_builder.py` | 435 | Timeline, entity, theme builders |
| `backend/services/news_scraper.py` | 445 | Article fetching + ChromaDB fallback |
| `backend/services/gkg_client.py` | 731 | BigQuery client with cost guards |
| `backend/routers/analyze.py` | 251 | FastAPI endpoints |
| `backend/schemas/responses.py` | 511 | Pydantic request/response models |

### Frontend

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/components/ExplorePanel.tsx` | 508 | Main explore UI with report buttons |
| `frontend/src/components/EventReportPanel.tsx` | 106 | Deep Dive report container |
| `frontend/src/components/StorylineTimeline.tsx` | 365 | Timeline/entities/themes tabs |
| `frontend/src/components/NewsCoveragePanel.tsx` | 116 | News source list |
| `frontend/src/components/GKGInsightCards.tsx` | 156 | GKG data cards |
| `frontend/src/api/client.ts` | 118 | API client methods |
| `frontend/src/types/index.ts` | 285 | TypeScript interfaces |
