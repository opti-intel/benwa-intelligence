// Constraints
CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (r:Resource) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (ri:Risk) REQUIRE ri.id IS UNIQUE;
CREATE CONSTRAINT milestone_id IF NOT EXISTS FOR (m:Milestone) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT zone_id IF NOT EXISTS FOR (z:Zone) REQUIRE z.id IS UNIQUE;

// Indexes
CREATE INDEX task_status IF NOT EXISTS FOR (t:Task) ON (t.status);
CREATE INDEX resource_type IF NOT EXISTS FOR (r:Resource) ON (r.type);
CREATE INDEX risk_severity IF NOT EXISTS FOR (ri:Risk) ON (ri.severity);

// Sample relationship types documented as comments:
// (t:Task)-[:DEPENDS_ON]->(t2:Task)
// (t:Task)-[:REQUIRES]->(r:Resource)
// (t:Task)-[:BELONGS_TO]->(p:Project)
// (t:Task)-[:LOCATED_IN]->(z:Zone)
// (t:Task)-[:HAS_MILESTONE]->(m:Milestone)
// (ri:Risk)-[:AFFECTS]->(t:Task)
// (ri:Risk)-[:MITIGATED_BY]->(t:Task)
// (r:Resource)-[:ALLOCATED_TO]->(z:Zone)
