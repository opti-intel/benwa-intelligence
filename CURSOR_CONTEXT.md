# Benwa Intelligence - Autonomous AI Construction Planning Platform

## Overview

Benwa Intelligence is an event-driven microservices platform that uses AI to autonomously generate, validate, and optimize construction plans. The system ingests project data (BIM models, sensor feeds, documents), maintains probabilistic belief states about project status, and runs constraint-satisfaction solvers to produce optimized schedules and resource allocations.

## Architecture

The platform follows an **event-driven microservices** architecture with **Apache Kafka** as the central message bus. Each service is independently deployable, communicates asynchronously via Kafka topics, and persists its own data. PostgreSQL (with pgvector for embeddings) serves as the primary relational store, Neo4j handles relationship graphs, and Redis provides caching and ephemeral state.

```
                         +-------------------+
                         |  Ingestion Gateway |  <-- BIM, sensors, docs
                         +---------+---------+
                                   |
                          [raw-ingestion topic]
                                   |
                    +--------------+--------------+
                    |                             |
          +---------v---------+         +---------v---------+
          |  Semantic Airlock  |         | Belief State Engine|
          +---------+---------+         +---------+---------+
                    |                             |
          [validated-plans]             [belief-updates]
                    |                             |
                    +--------------+--------------+
                                   |
                         [solver-requests topic]
                                   |
                         +---------v---------+
                         |   Solver Engine    |
                         +---------+---------+
                                   |
                          [solver-results topic]
                                   |
                         +---------v---------+
                         |     Dashboard      |
                         +-------------------+
```

## Services

### Ingestion Gateway (port 8004)

Entry point for all external data flowing into the system. Accepts BIM models (IFC format), IoT sensor data, project documents (PDF, DOCX), and structured project metadata. Handles parsing, normalization, and enrichment before publishing to the `raw-ingestion` Kafka topic.

- **Tech**: Python / FastAPI
- **Kafka**: Produces to `raw-ingestion`
- **Storage**: PostgreSQL for metadata, file references

### Semantic Airlock (port 8001)

Validates and gates AI-generated construction plans before they enter the broader system. Performs semantic validation against building codes, safety rule checks, and compliance verification using LLM-based reasoning (Anthropic Claude). Acts as a quality firewall ensuring only sound plans propagate downstream.

- **Tech**: Python / FastAPI
- **Kafka**: Consumes `raw-ingestion`, produces to `validated-plans`
- **Storage**: PostgreSQL for validation audit logs
- **AI**: Anthropic Claude API for semantic reasoning

### Belief State Engine (port 8002)

Maintains probabilistic belief states about construction project status, resource availability, weather impacts, and risk factors. Continuously updates beliefs as new data arrives. Uses Neo4j to model relationships between project entities (tasks, resources, constraints, risks) as a knowledge graph.

- **Tech**: Python / FastAPI
- **Kafka**: Consumes `validated-plans`, produces to `belief-updates`
- **Storage**: PostgreSQL for time-series belief snapshots, Neo4j for relationship graphs
- **AI**: Bayesian inference, probabilistic graphical models

### Solver Engine (port 8003)

Constraint satisfaction and optimization engine for construction scheduling, resource allocation, and plan optimization. Takes belief states and validated plans as inputs, applies constraint propagation and optimization algorithms to produce actionable schedules.

- **Tech**: Python / FastAPI
- **Kafka**: Consumes `belief-updates` and `solver-requests`, produces to `solver-results`
- **Storage**: PostgreSQL for solver run history and results
- **Algorithms**: CP-SAT (OR-Tools), custom heuristics

### Dashboard (port 3000)

Real-time web interface for monitoring project status, viewing optimized plans, inspecting belief states, and managing the pipeline. Built with React and connects to service APIs.

- **Tech**: TypeScript / React / Vite
- **Components**: Located in `dashboard/src/components/`
- **Pages**: Located in `dashboard/src/pages/`
- **Hooks**: Located in `dashboard/src/hooks/`

## Tech Stack

| Layer         | Technology                              |
|---------------|----------------------------------------|
| Language      | Python 3.12 (services), TypeScript (dashboard) |
| API Framework | FastAPI                                 |
| Message Bus   | Apache Kafka (Confluent Platform 7.5)   |
| Relational DB | PostgreSQL 16 with pgvector             |
| Graph DB      | Neo4j 5.15 Community                    |
| Cache         | Redis 7                                 |
| AI/LLM        | Anthropic Claude (via API)              |
| Optimization  | Google OR-Tools (CP-SAT)                |
| Frontend      | React + Vite + TypeScript               |
| Containers    | Docker + Docker Compose                 |

## Kafka Topics

| Topic              | Producer            | Consumer(s)                        | Description                                    |
|--------------------|---------------------|------------------------------------|------------------------------------------------|
| `raw-ingestion`    | ingestion-gateway   | semantic-airlock, belief-state-engine | Raw incoming data after parsing                |
| `validated-plans`  | semantic-airlock    | belief-state-engine                | Plans that passed semantic validation          |
| `belief-updates`   | belief-state-engine | solver-engine                      | Updated belief state snapshots                 |
| `solver-requests`  | belief-state-engine | solver-engine                      | Explicit requests for solver optimization runs |
| `solver-results`   | solver-engine       | dashboard, belief-state-engine     | Optimized schedules and allocations            |

## Database Schemas

### PostgreSQL

The init script at `db/postgres/init.sql` sets up the base schema. Key tables include:

- **ingestion_records** - Tracks all ingested documents and data sources
- **validation_logs** - Audit trail of semantic airlock decisions
- **belief_snapshots** - Point-in-time belief state captures
- **solver_runs** - History of solver executions with parameters and results
- **projects** - Top-level project metadata

The pgvector extension is enabled for storing and querying document embeddings used by the semantic airlock.

### Neo4j

The belief-state-engine manages the following node types and relationships:

- **Nodes**: `Project`, `Task`, `Resource`, `Constraint`, `Risk`, `Milestone`
- **Relationships**: `DEPENDS_ON`, `REQUIRES`, `BLOCKS`, `MITIGATES`, `BELONGS_TO`

## Directory Structure

```
benwa-intelligence/
├── .env.example              # Placeholder credentials (copy to .env)
├── .gitignore
├── docker-compose.yml
├── CURSOR_CONTEXT.md         # This file
├── services/
│   ├── semantic-airlock/     # Semantic validation service
│   ├── belief-state-engine/  # Probabilistic belief state manager
│   ├── solver-engine/        # Constraint solver and optimizer
│   └── ingestion-gateway/    # External data ingestion
├── dashboard/
│   └── src/
│       ├── components/       # Reusable React components
│       ├── pages/            # Route-level page components
│       └── hooks/            # Custom React hooks
├── db/
│   ├── postgres/             # PostgreSQL init scripts and migrations
│   └── neo4j/                # Neo4j seed data and constraints
└── tests/                    # Integration and end-to-end tests
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Node.js 20+ (for dashboard development)

### Environment Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your actual credentials:
   - Set `ANTHROPIC_API_KEY` to your Anthropic API key
   - Set Neo4j credentials as desired for local development
   - Adjust PostgreSQL credentials if needed

3. Start all services:
   ```bash
   docker-compose up --build
   ```

4. Verify services are running:
   - Dashboard: http://localhost:3000
   - Ingestion Gateway: http://localhost:8004/docs
   - Semantic Airlock: http://localhost:8001/docs
   - Belief State Engine: http://localhost:8002/docs
   - Solver Engine: http://localhost:8003/docs
   - Neo4j Browser: http://localhost:7474

### Running Tests

Each service has its own test suite using pytest:

```bash
# Run all tests
cd tests && pytest

# Run tests for a specific service
cd services/semantic-airlock && pytest
cd services/belief-state-engine && pytest
cd services/solver-engine && pytest
cd services/ingestion-gateway && pytest
```

### Local Development

For developing a single service locally (outside Docker), ensure the infrastructure is running:

```bash
# Start only infrastructure services
docker-compose up -d zookeeper kafka postgres neo4j redis

# Then run the service locally
cd services/semantic-airlock
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```
