-- Add interview_chain column to job table
ALTER TABLE job ADD COLUMN IF NOT EXISTS interview_chain TEXT;
