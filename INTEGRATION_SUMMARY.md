# Integration Summary - Job Scoring System & Scheduler Updates

## Overview
This document summarizes the integration of the new llama_cpp scoring system and scheduler timezone support.

---

## 1. NVIDIA Driver Mismatch Error - SOLUTION

### Problem
```
nvidia-container-cli: initialization error: nvml error: driver/library version mismatch: unknown
```

### Root Cause
This error occurs when the NVIDIA driver on the host doesn't match the NVIDIA container runtime version.

### Solutions (try in order):

#### Option 1: Restart Docker (Recommended)
```bash
# Windows (PowerShell as Administrator)
Restart-Service docker

# Linux
sudo systemctl restart docker
```

#### Option 2: Rebuild Containers
```bash
docker-compose down
docker-compose up --build
```

#### Option 3: Temporary Workaround (for testing without GPU)
If you need to run without GPU temporarily, comment out the `deploy` section in docker-compose.yml:

```yaml
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: all
#           capabilities: [gpu]
```

#### Option 4: Update NVIDIA Container Runtime
```bash
# Update NVIDIA drivers on host
# Then update nvidia-container-toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

---

## 2. New Scoring System Integration

### Changes Made

#### Backend Changes
1. **llama_cpp_scoring.py** - Added `to_legacy_format()` method
   - Converts 0-10 scores to 0-100 scale
   - Includes evidence/reasoning for each category
   - Six categories: Skillset Match, Academic Requirements, Experience Level, Professional Experience, Language Requirements, Preference Alignment

2. **socketio_events.py** - Updated to use CandidateEvaluator
   - Replaced Gemini API with llama.cpp
   - Uses `CandidateEvaluator` class for scoring
   - Maintains backward compatibility with old format

3. **docker-compose.yml** - Dual LLM setup
   - **Ollama** (port 11435 external, 11434 internal) - For CV extraction
   - **llama-cpp-server** (port 11434 external, 11434 internal) - For job scoring
   - No port conflicts via Docker internal networking

#### Frontend Changes
1. **index.html** - Enhanced score display
   - New CSS classes for evidence-based scoring
   - Each category shows score + color-coded badge + evidence text
   - Color coding: Green (≥80%), Yellow (≥60%), Red (<60%)
   - Maintains backward compatibility with old Gemini format

### New Scoring Structure
```json
{
  "skillset": 90,
  "academic": 85,
  "experience": 70,
  "professional": 80,
  "language": 95,
  "preference": 88,
  "overall": 85,
  "reasoning": {
    "skillset_match": {
      "score": 90,
      "evidence": "Job: Expertise in RAG pipelines. Candidate: Built production RAG tools at Munich Re."
    },
    ...
  }
}
```

---

## 3. Scheduler Timezone Support

### Changes Made

#### Database Schema
- **models.py**: Added `schedule_timezone` field to `SearchCriteria` model
  - Type: VARCHAR(50)
  - Default: 'UTC'
  - Stores IANA timezone (e.g., 'Europe/Berlin', 'America/New_York')

#### Scheduler Logic
- **scheduler.py**: Updated `CronTrigger` to use timezone
  - Reads `schedule_timezone` from database
  - Applies timezone to all cron triggers
  - Supports daily, weekly, and monthly schedules

#### Frontend
- **scrape.html**: Added timezone selector
  - 13 common timezones available
  - Shows timezone in schedule display (e.g., "Daily at 09:00 Europe/Berlin")
  - Persists timezone selection when saving/loading templates

#### Database Migration
- **migrations/add_timezone_to_search_criteria.sql**
  - Run this to update existing database:
    ```bash
    docker-compose exec db psql -U user -d jobs -f /app/migrations/add_timezone_to_search_criteria.sql
    ```
  - Or apply via GUI tool (pgAdmin, DBeaver, etc.)

### Supported Timezones
- UTC (Coordinated Universal Time)
- Europe/Berlin (CET/CEST)
- Europe/London (GMT/BST)
- Europe/Paris (CET/CEST)
- Europe/Zurich (CET/CEST)
- America/New_York (EST/EDT)
- America/Chicago (CST/CDT)
- America/Denver (MST/MDT)
- America/Los_Angeles (PST/PDT)
- Asia/Tokyo (JST)
- Asia/Shanghai (CST)
- Asia/Singapore (SGT)
- Australia/Sydney (AEDT/AEST)

---

## Testing

### 1. Start Services
```bash
docker-compose down -v  # Clean start (optional)
docker-compose up --build
```

### 2. Apply Database Migration (if upgrading existing database)
```bash
docker-compose exec db psql -U user -d jobs -f /app/migrations/add_timezone_to_search_criteria.sql
```

### 3. Test Scoring System
1. Navigate to `/prompt` or `/scrape`
2. Upload CV and add preferences
3. Run a scrape
4. Check that jobs are scored with the new 6-category system
5. Click on a job to see detailed evidence for each score

### 4. Test Scheduler
1. Go to `/scrape`
2. Create a new search template
3. Enable "Automatic Scheduling"
4. Set time and select timezone
5. Save the template
6. Verify schedule appears with timezone (e.g., "Daily at 09:00 Europe/Berlin")

---

## Port Configuration

| Service | Host Port | Container Port | Purpose |
|---------|-----------|----------------|---------|
| PostgreSQL | 5433 | 5432 | Database |
| Flask | 5000 | 5000 | Web UI |
| Selenium | 4444 | 4444 | LinkedIn scraping |
| llama-cpp | 11434 | 11434 | Job scoring |
| Ollama | 11435 | 11434 | CV extraction |

---

## Environment Variables

```bash
# Required for scoring
LLAMA_CPP_HOST=http://llama-cpp-server:11434

# Required for CV extraction (if using Ollama)
OLLAMA_HOST=http://ollama:11434

# Required for database
DATABASE_URL=postgresql://user:password@db:5432/jobs
```

---

## Troubleshooting

### Scoring not working
1. Check llama-cpp-server is running: `docker-compose ps`
2. Check logs: `docker-compose logs llama-cpp-server`
3. Verify model is loaded: `docker-compose exec llama-cpp-server curl http://localhost:11434/health`

### Scheduler not running
1. Check scheduler logs in Flask app: `docker-compose logs app | grep scheduler`
2. Verify timezone is valid IANA format
3. Check last_run timestamp in database

### NVIDIA errors persist
1. Restart host machine
2. Update NVIDIA drivers
3. Temporarily disable GPU (comment out `deploy` sections)

---

## Files Modified

### Backend
- `src/llama_cpp_scoring.py` - Added `to_legacy_format()` method
- `src/socketio_events.py` - Integrated CandidateEvaluator
- `src/models.py` - Added `schedule_timezone` field
- `src/scheduler.py` - Added timezone support to cron triggers
- `docker-compose.yml` - Configured dual LLM setup

### Frontend
- `templates/index.html` - Enhanced score display with evidence
- `templates/scrape.html` - Added timezone selector

### New Files
- `migrations/add_timezone_to_search_criteria.sql` - Database migration

---

## Next Steps

1. Run `docker-compose up --build` to start all services
2. Apply database migration if upgrading
3. Test job scoring with new llama_cpp system
4. Test scheduler with timezone support
5. Monitor logs for any issues

---

**Date**: 2025-02-05
**Version**: 1.0
