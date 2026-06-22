import asyncio
from src.state import BaseAgent, ResearchState


class LibrarianAgent(BaseAgent):
    """
    AGENT: LibrarianAgent (Flash Layer)

    The Context Librarian. Compiles raw scraped web feeds into clear, structured
    reference indices. Employs an implicit structural token strategy to trigger
    Gemini's automatic backend prefix-caching layers, avoiding API quota blocks.
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        super().__init__(name="LibrarianAgent", model=model)

    async def execute(self, state: ResearchState) -> ResearchState:
        print(f"📚 [{self.name}] Structuring cache stream for {len(state.raw_documents)} raw sources...")

        if not state.raw_documents:
            print(f"⚠️ [{self.name}] Empty input stream. Moving to routing sequence.")
            state.active_routing_target = "auditor"
            return state

        # 1. Compile raw data into a strictly structured immutable document reference index
        # Placing common static information here maximizes implicit prefix cache hits.
        compiled_content = "=== AURA CORE ENGINE RESEARCH DOCUMENTATION CACHE ===\n"
        for i, doc in enumerate(state.raw_documents):
            compiled_content += f"\n[DOCUMENT REF INDEX: {i + 1}]\n"
            compiled_content += f"METADATA_TITLE: {doc.get('title', 'Untitled Reference')}\n"
            compiled_content += f"METADATA_URL: {doc.get('url', 'Direct Fetch Platform Entry')}\n"
            compiled_content += f"RAW_MARKDOWN_BODY:\n{doc.get('content', '')}\n"
            compiled_content += "====================================================\n"

        # 2. Store compiled cache in the dedicated compiled_cache field
        state.compiled_cache = compiled_content

        state.active_routing_target = "auditor"  # Advance the execution router status

        print(f"✅ [{self.name}] Index compilation secure. Size: {len(compiled_content)} characters.")
        print(f"⏳ [{self.name}] Data structured for Gemini implicit prefix token optimization.")

        return state