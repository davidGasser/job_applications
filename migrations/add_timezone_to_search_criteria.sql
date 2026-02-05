-- Migration: Add timezone support to SearchCriteria table
-- Date: 2025-02-05
-- Description: Adds schedule_timezone column to support timezone-aware scheduling

-- Add the new column with default value 'UTC'
ALTER TABLE search_criteria
ADD COLUMN IF NOT EXISTS schedule_timezone VARCHAR(50) NOT NULL DEFAULT 'UTC';

-- Optional: Update existing scheduled jobs to use a specific timezone
-- Uncomment and modify if you want to set a different default timezone for existing entries
-- UPDATE search_criteria
-- SET schedule_timezone = 'Europe/Berlin'
-- WHERE schedule_enabled = TRUE;
