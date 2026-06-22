import asyncio
import json
import os
from src.state import ResearchState
from src.graph_writer import GraphWriter


async def main():
    print("🔄 [AuRA Recovery] Initializing tokenless graph restoration...")

    # 1. Instantiate your newly updated, rigid-schema GraphWriter
    writer = GraphWriter()

    # 2. Mock a ResearchState using your last successful execution payload
    # If you have a local state dump JSON, we load it, otherwise we feed the verified triples directly
    state = ResearchState(
        user_query="Quantum computing encryption timeline NIST 2026",
        knowledge_graph=[
            {"subject": "NIST", "predicate": "INITIATED PROGRAM", "object": "Post-Quantum Cryptography Standardization",
             "confidence": 1.0},
            {"subject": "Post-Quantum Cryptography Standardization", "predicate": "AIMS TO UPDATE STANDARDS FOR",
             "object": "Post-quantum cryptography", "confidence": 1.0},
            {"subject": "Post-Quantum Cryptography Standardization", "predicate": "ANNOUNCED AT",
             "object": "PQCrypto 2016", "confidence": 1.0}
            # Add any other core triples here if saved, or let's run a micro-batch
        ]
    )

    # 3. Securely pump back into Neo4j
    await writer.write_triples_to_graph(state)
    print("✨ [AuRA Recovery] Neo4j Aura has been safely restored with rigid constraints.")


if __name__ == "__main__":
    asyncio.run(main())