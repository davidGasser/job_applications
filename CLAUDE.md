# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a job application tracking system that scrapes job listings from LinkedIn, stores them in a PostgreSQL database, and provides a web interface to manage applications through different views (list, kanban, calendar). The system automatically analyzes job descriptions and can score job fit against a resume.

## Running the Application

### Development
```bash
# Start all services (Flask app, PostgreSQL, Selenium)
docker-compose up --build

# Access the application
# Web UI: http://localhost:5000
# PostgreSQL: localhost:5433
# Selenium Hub: http://localhost:4444
```

### Database Management
The database schema is automatically created on first run via `db.create_all()` in `src/main.py:437-438`.

To reset the database:
```bash
docker-compose down -v  # Remove volumes
docker-compose up --build
```

## Architecture

### Multi-Container Setup
- **app**: Flask application with SocketIO for real-time scraping updates
- **db**: PostgreSQL 16 database
- **selenium**: Standalone Chrome for LinkedIn scraping (requires authenticated session)

### Core Components

**src/main.py** - Flask application with three main responsibilities:
1. REST API for CRUD operations on jobs, search criteria, contacts, and dates
2. Real-time WebSocket communication via SocketIO for scraping progress
3. Web UI routing (index, scrape form, kanban board, calendar)

**src/scrapers.py** - `LinkedInScraper` class handles:
- URL construction with LinkedIn filter parameters (distance, date, experience level, job type)
- Cookie-based authentication (manual login on first run, saves to `linkedin_cookies.json`)
- Selenium automation to scrape job listings across multiple pages/locations
- Real-time logging via custom `SocketIOHandler` that emits progress to frontend

**src/cv_ocr.py** - CV/resume analysis (experimental/incomplete):
- PDF to image conversion
- Line detection and whitespace analysis for layout parsing

### Database Schema

Key models (see `src/main.py:34-76`):
- `Job`: Core entity with title, company, location, description, application_link, status (New/Interested/Applied/Archived)
- `SearchCriteria`: Stores search parameters used to find jobs
- `JobDate`: Calendar events/deadlines associated with jobs
- `Contact`: Recruiter/contact information per job
- Relationships: Jobs have many dates and contacts (cascade delete)

### Frontend Structure
Templates in `templates/`:
- `base.html` / `base_fullwidth.html`: Base layouts with navigation
- `index.html`: List view of all jobs
- `kanban.html`: Drag-and-drop status board (New → Interested → Applied → Archived)
- `calendar.html`: Timeline view for job-related dates
- `scrape.html`: Form interface to configure and start LinkedIn scraping

No static assets directory exists yet - all styling/scripts are inline in templates.

## LinkedIn Scraper Usage

The scraper connects to a remote Selenium instance (`http://selenium:4444/wd/hub`) and uses LinkedIn's job search with filters:

**Filter mappings** (defined in `src/scrapers.py:42-45`):
- Distance: `{0: 0, 8: 5, 16: 10, 40: 25, 80: 50, 160: 100}` (km to miles)
- Date posted: `{"past month": 2592000, "past week": 604800, "past 24 hours": 86400}` (seconds)
- Experience level: `{"internship": 1, "entry level": 2, "associate": 3, "mid-senior level": 4, "director": 5, "executive": 6}`
- Job type: `{"full-time": "F", "part-time": "P", "contract": "C", "temporary": "T", "other": "O", "internship": "I"}`

**First-time setup**: When scraping for the first time, the scraper will open LinkedIn's login page and wait 180 seconds for manual authentication. Cookies are saved to `linkedin_cookies.json` for subsequent runs.

**Scraping flow**:
1. Frontend emits `start_scrape` WebSocket event with search parameters
2. Backend creates/finds `SearchCriteria` record
3. `LinkedInScraper` scrapes jobs across all locations and pages
4. Jobs are deduplicated by `application_link` before database insertion
5. Progress logs stream to frontend via SocketIO `log_message` events
6. Completion triggers `scrape_finished` event

## Key Implementation Details

### Real-time Logging
The scraper uses a custom `SocketIOHandler` (see `src/main.py:19-22`) that intercepts log messages from `scrapers.py` and emits them to connected WebSocket clients, enabling live progress updates in the UI.

### Job Deduplication
- During scraping: Jobs with duplicate `(company, title)` are removed from the DataFrame
- Before database insert: Checks if `application_link` already exists to prevent duplicate entries

### Application Link Extraction
The scraper attempts two methods (see `src/scrapers.py:222-241`):
1. Check for "Easy Apply" button → uses current URL
2. Click external "Apply" button → switches to new tab, captures URL, closes tab
3. If both fail → stores "Not Available" (these jobs are skipped during import)

### Database Connection
Uses environment variable `DATABASE_URL=postgresql://user:password@db:5432/jobs` configured in docker-compose.yml.

## Development Notes

### Templates Location
Flask is configured with custom template folder: `template_folder='../templates'` (relative to src/)

### CV Analysis (Incomplete)
The `cv_ocr.py` module is experimental and not integrated into the main application. It contains image processing code for CV layout analysis but lacks OCR integration.

### Status Workflow
Job statuses represent the application pipeline:
- **New**: Recently scraped, not yet reviewed
- **Interested**: Worth applying to
- **Applied**: Application submitted
- **Archived**: Not pursuing further
