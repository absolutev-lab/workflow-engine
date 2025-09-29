-- Initialize database with required extensions and settings

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable JSONB functions
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create indexes for better performance
-- These will be created after tables are created by SQLAlchemy

-- Set timezone
SET timezone = 'UTC';

-- Create database user if not exists (handled by Docker environment)
-- This file is mainly for extensions and initial setup