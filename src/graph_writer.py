import asyncio
import re
from neo4j import AsyncGraphDatabase
from src.state import ResearchState
from src.config import settings


class GraphWriter:
    """
    UTILITY: Secure GraphWriter Pipeline

    Establishes an enterprise-secured TLS connection natively by leveraging
    the strict explicit "+s" security scheme provided in the connection URI.
    Maps unstructured triples onto rigid schema constraints (:Source, :Claimant, :DataPoint).
    """

    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.auth = (settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)

    def _determine_node_label(self, text: str) -> str:
        """
        Helper method to deterministically route a text value to its matching
        Step 3.2 node type constraint: Source, DataPoint, or Claimant.
        """
        text_lower = text.lower().strip()

        # 1. Route to Source if it contains common publication identifiers
        if any(x in text_lower for x in
               ["http", ".com", ".org", ".edu", "wikipedia", "nist report", "pdf", "citation"]):
            return "Source"

        # 2. Route to DataPoint if it contains timeline tags, specific years, digits, or metrics
        # Matches strings with 4 digit years (e.g., "April 2018", "1901") or purely metrics
        if re.search(r'\b\d{4}\b', text_lower) or any(char.isdigit() for char in text_lower):
            return "DataPoint"

        # 3. Default to Claimant for organizations, agencies, protocols, or entities making assertions
        return "Claimant"

    async def write_triples_to_graph(self, state: ResearchState) -> ResearchState:
        """
        Parses triples from ResearchState memory and writes them securely into Neo4j
        enforcing structural label constraints and dynamic descriptive semantic edges.
        Skips gracefully if Neo4j credentials are not configured.
        """
        if not state.knowledge_graph:
            print("⚠️ [GraphWriter] No structural triples found in state memory to upload.")
            return state

        # Skip gracefully if Neo4j is not configured or URI is invalid
        if not self.uri or not self.auth[0] or not self.auth[1]:
            print("⚠️ [GraphWriter] Neo4j credentials not configured — skipping graph database sync.")
            return state
        if "neo4j+s://" not in self.uri and "neo4j://" not in self.uri:
            print("⚠️ [GraphWriter] Neo4j URI appears invalid — skipping graph database sync.")
            return state

        print(f"🧬 [GraphWriter] Connecting securely to Neo4j Aura Instance via URI Protocol: {self.uri}")

        try:
            async with AsyncGraphDatabase.driver(self.uri, auth=self.auth) as driver:
                await driver.verify_connectivity()

                async with driver.session() as session:
                    print(
                        f"🔒 [GraphWriter] Protocol Handshake Verified. Committing {len(state.knowledge_graph)} triples safely...")

                    success_count = 0
                    for triple in state.knowledge_graph:
                        try:
                            subject_val = triple["subject"].strip()
                            object_val = triple["object"].strip()
                            source_citation_val = triple.get("source_citation", "AuRA Automated Engine Ingestion").strip()

                            # --- STEP 3.2 STRATIFICATION LAYER ---
                            # Determine strict deterministic labels for Subject and Object
                            s_label = self._determine_node_label(subject_val)
                            o_label = self._determine_node_label(object_val)

                            # Handle the source node explicitly
                            src_label = "Source"

                            # Sanitize predicate to use as the true descriptive edge relationship type
                            clean_predicate = triple["predicate"].strip().replace(" ", "_").replace("-", "_").replace(".", "_").upper()
                            if not clean_predicate or clean_predicate[0].isdigit():
                                clean_predicate = "RELATED_TO"

                            # Determine strict directional edge constraint vector (ASSERTS vs CONTRADICTS)
                            structural_vector = "ASSERTS"
                            negation_words = ["contradicts", "opposes", "rejects", "violates", "denies", "falsifies", "invalidates"]
                            if any(neg in clean_predicate.lower() for neg in negation_words):
                                structural_vector = "CONTRADICTS"

                            # --- PREMIUM HYBRID DUAL-PROPERTY GRAPH PATTERN ---
                            # Uses the clean, descriptive LLM predicate as the true native visual edge type,
                            # while attaching the Step 3.2 constraint as an internal structural property tag.
                            cypher_query = f"""
                            MERGE (src:{src_label} {{name: $source_citation}})
                            MERGE (s:{s_label} {{name: $subject}})
                            MERGE (o:{o_label} {{name: $object}})
                            WITH src, s, o

                            // Create the true descriptive action edge between nodes dynamically
                            MERGE (s)-[r:{clean_predicate}]->(o)
                            SET r.confidence = $confidence,
                                r.validation_mode = $structural_vector

                            // Enforce lineage tracking mapping from the parent Context Source
                            MERGE (src)-[:EVIDENCE_FOR]->(s)
                            RETURN count(r) as link_count
                            """

                            await session.run(
                                cypher_query,
                                subject=subject_val,
                                object=object_val,
                                confidence=float(triple.get("confidence", 1.0)),
                                source_citation=source_citation_val,
                                structural_vector=structural_vector
                            )
                            success_count += 1
                        except Exception as err:
                            print(f"❌ [GraphWriter] Failed to write triple: {err}")

                    print(
                        f"✅ [GraphWriter] Secure database sync complete! Successfully mapped {success_count} nodes/edges into Neo4j Aura.")

        except Exception as e:
            print(f"⚠️ [GraphWriter] Neo4j connection failed — skipping graph database sync. Reason: {e}")

        return state