import asyncio
from src.state import ResearchState
from src.orchestrator import aura_app


async def test_full_graph_pipeline():
    print("⚡ Executing E2E AuRA LangGraph StateGraph Engine...")

    # 1. Initialize Global State
    state = ResearchState(user_query="Quantum computing encryption timeline NIST 2026")

    # 2. Run the LangGraph application E2E
    final_state = await aura_app.ainvoke(state)

    print("\n🚀 [STATUS]: E2E LangGraph Pipeline Completed Successfully!")

    # 3. Print verification stats safely (handling both dict and object returns)
    if isinstance(final_state, dict):
        kg_len = len(final_state.get("knowledge_graph") or [])
        conflicts_len = len(final_state.get("conflicts") or [])
        tie_breakers_len = len(final_state.get("tie_breaker_queries") or [])
        final_report = final_state.get("final_report")
    else:
        kg_len = len(getattr(final_state, "knowledge_graph", []) or [])
        conflicts_len = len(getattr(final_state, "conflicts", []) or [])
        tie_breakers_len = len(getattr(final_state, "tie_breaker_queries", []) or [])
        final_report = getattr(final_state, "final_report", None)

    print(f"📊 Triples Extracted: {kg_len}")
    print(f"⚠️ Contradictions Flagged: {conflicts_len}")
    print(f"🔄 Loopback Queries Executed: {tie_breakers_len}")

    if final_report:
        print("\n📄 Final Report Sample (First 500 chars):\n")
        print(final_report[:500])
    else:
        print("\n❌ Final Report was not generated!")


if __name__ == "__main__":
    asyncio.run(test_full_graph_pipeline())