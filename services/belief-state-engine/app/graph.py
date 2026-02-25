"""Neo4j graph operations for the Belief State Engine."""

from typing import Optional

from neo4j import Driver, GraphDatabase

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.config import get_settings


class Neo4jClient:
    """Client for Neo4j graph database operations."""

    def __init__(self, driver: Driver):
        self._driver = driver

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------
    def create_node(self, label: str, properties: dict) -> dict:
        """Create a node with the given label and properties. Returns the created node."""
        props_string = ", ".join(f"{k}: ${k}" for k in properties)
        query = f"CREATE (n:{label} {{{props_string}}}) RETURN n"

        with self._driver.session() as session:
            result = session.run(query, **properties)
            record = result.single()
            if record is None:
                return {}
            node = record["n"]
            return dict(node)

    # ------------------------------------------------------------------
    # Relationship operations
    # ------------------------------------------------------------------
    def create_relationship(
        self,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        rel_type: str,
        properties: Optional[dict] = None,
    ) -> dict:
        """
        Create a relationship between two nodes identified by entity_id.

        Nodes are matched by their entity_id property. If either node does not
        exist, it will be created with MERGE.
        """
        properties = properties or {}
        props_string = ", ".join(f"{k}: ${k}" for k in properties)
        rel_props = f" {{{props_string}}}" if props_string else ""

        query = (
            f"MERGE (a:{from_label} {{entity_id: $from_id}}) "
            f"MERGE (b:{to_label} {{entity_id: $to_id}}) "
            f"CREATE (a)-[r:{rel_type}{rel_props}]->(b) "
            f"RETURN type(r) AS rel_type, a.entity_id AS from_id, b.entity_id AS to_id"
        )

        params = {"from_id": from_id, "to_id": to_id, **properties}
        with self._driver.session() as session:
            result = session.run(query, **params)
            record = result.single()
            if record is None:
                return {}
            return {
                "rel_type": record["rel_type"],
                "from_id": record["from_id"],
                "to_id": record["to_id"],
            }

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------
    def get_neighbors(
        self,
        label: str,
        entity_id: str,
        rel_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Return connected nodes (neighbors) of a given node.

        Optionally filter by relationship type.
        """
        rel_filter = f":{rel_type}" if rel_type else ""
        query = (
            f"MATCH (n:{label} {{entity_id: $entity_id}})-[r{rel_filter}]-(m) "
            f"RETURN labels(m) AS labels, m.entity_id AS entity_id, "
            f"type(r) AS rel_type, properties(m) AS props"
        )

        neighbors: list[dict] = []
        with self._driver.session() as session:
            records = session.run(query, entity_id=entity_id)
            for record in records:
                labels = record["labels"]
                neighbors.append({
                    "label": labels[0] if labels else "Unknown",
                    "entity_id": record["entity_id"],
                    "rel_type": record["rel_type"],
                    "properties": dict(record["props"]) if record["props"] else {},
                })

        return neighbors

    def get_subgraph(
        self,
        label: str,
        entity_id: str,
        depth: int = 2,
    ) -> dict:
        """
        Return a subgraph up to the specified depth around a given node.

        Returns nodes and relationships within the subgraph.
        """
        query = (
            f"MATCH path = (n:{label} {{entity_id: $entity_id}})-[*1..{depth}]-(m) "
            f"RETURN nodes(path) AS nodes, relationships(path) AS rels"
        )

        all_nodes: dict[str, dict] = {}
        all_rels: list[dict] = []

        with self._driver.session() as session:
            records = session.run(query, entity_id=entity_id)
            for record in records:
                for node in record["nodes"]:
                    node_id = node.get("entity_id", str(node.id))
                    if node_id not in all_nodes:
                        all_nodes[node_id] = {
                            "labels": list(node.labels),
                            "entity_id": node_id,
                            "properties": dict(node),
                        }
                for rel in record["rels"]:
                    all_rels.append({
                        "type": rel.type,
                        "start_node": rel.start_node.get("entity_id", str(rel.start_node.id)),
                        "end_node": rel.end_node.get("entity_id", str(rel.end_node.id)),
                        "properties": dict(rel),
                    })

        return {
            "root": {"label": label, "entity_id": entity_id},
            "depth": depth,
            "nodes": list(all_nodes.values()),
            "relationships": all_rels,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        self._driver.close()


def get_neo4j_driver() -> Driver:
    """Create and return a Neo4j driver from shared config settings."""
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    return driver
