-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Ingestion records
CREATE TABLE ingestion_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL,  -- 'bim', 'sensor', 'document', 'manual'
    source_uri TEXT,
    raw_payload JSONB NOT NULL,
    normalized_payload JSONB,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'validated', 'rejected', 'failed'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Semantic validation results
CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingestion_id UUID REFERENCES ingestion_records(id),
    validation_type VARCHAR(50) NOT NULL,  -- 'safety', 'compliance', 'semantic', 'structural'
    passed BOOLEAN NOT NULL,
    confidence FLOAT,
    findings JSONB,
    ai_reasoning TEXT,
    embedding vector(1536),  -- pgvector for semantic search
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Construction plans
CREATE TABLE construction_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL,
    plan_name VARCHAR(255) NOT NULL,
    plan_version INTEGER DEFAULT 1,
    plan_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'validated', 'optimized', 'approved', 'active'
    semantic_hash VARCHAR(64),
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Belief states
CREATE TABLE belief_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,  -- 'project', 'resource', 'task', 'risk'
    entity_id VARCHAR(255) NOT NULL,
    belief_vector JSONB NOT NULL,  -- probabilistic state
    confidence FLOAT NOT NULL,
    evidence JSONB,
    embedding vector(1536),
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Solver results
CREATE TABLE solver_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID REFERENCES construction_plans(id),
    solver_type VARCHAR(50) NOT NULL,  -- 'scheduling', 'resource_allocation', 'optimization'
    objective_value FLOAT,
    constraints_satisfied INTEGER,
    constraints_total INTEGER,
    solution JSONB NOT NULL,
    metadata JSONB,
    compute_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tasks (construction tasks managed via dashboard)
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    naam VARCHAR(255) NOT NULL,
    beschrijving TEXT DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'gepland',  -- 'gepland', 'bezig', 'klaar'
    startdatum DATE,
    einddatum DATE,
    toegewezen_aan VARCHAR(255) DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_ingestion_status ON ingestion_records(status);
CREATE INDEX idx_ingestion_source ON ingestion_records(source_type);
CREATE INDEX idx_validation_ingestion ON validation_results(ingestion_id);
CREATE INDEX idx_plans_project ON construction_plans(project_id);
CREATE INDEX idx_plans_status ON construction_plans(status);
CREATE INDEX idx_belief_entity ON belief_states(entity_type, entity_id);
CREATE INDEX idx_solver_plan ON solver_results(plan_id);
CREATE INDEX idx_tasks_status ON tasks(status);
