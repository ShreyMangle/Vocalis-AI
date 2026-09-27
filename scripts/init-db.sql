-- =============================================================================
-- VoxAI — Database Initialization Script
-- =============================================================================
-- This file runs ONCE when the PostgreSQL container starts for the first time.
-- It sets up extensions and basic configurations.
--
-- CONCEPT: PostgreSQL Extensions
-- --------------------------------
-- PostgreSQL can be extended with plugins called "extensions".
-- We need two:
--   1. uuid-ossp  → generates UUID values (like random IDs for rows)
--   2. vector     → pgvector, stores AI embeddings for RAG knowledge search
--
-- "CREATE EXTENSION IF NOT EXISTS" = only create if not already exists (safe to re-run)

-- Enable UUID generation functions
-- gen_random_uuid() will be used as default value for primary key columns
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable pgvector for AI embedding storage (RAG knowledge base)
-- This lets us store vectors (lists of numbers) and do similarity search
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================================================
-- VERIFY SETUP (optional — appears in docker logs on first start)
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE 'VoxAI database initialized successfully';
    RAISE NOTICE 'Extensions: uuid-ossp, pgcrypto, vector (pgvector) ✓';
END
$$;
