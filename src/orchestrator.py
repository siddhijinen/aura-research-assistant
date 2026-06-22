import os
import asyncio
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import ResearchState

# Import your corrected agents
from src.scout import ScoutAgent
from src.librarian import LibrarianAgent
from src.auditor import AuditorAgent
from src.synthesizer import SynthesizerAgent
from src.divergence_gate import DivergenceGate

# Force stable model keys
scout = ScoutAgent(model="gemini-2.5-flash")
librarian = LibrarianAgent(model="gemini-2.5-flash")
auditor = AuditorAgent(model="gemini-2.5-flash")
synthesizer = SynthesizerAgent(model="gemini-2.5-flash")
divergence_checker = DivergenceGate(conflict_threshold=0.20)


async def generate_tie_breaker_query(state: ResearchState, conflicts: List[Dict[str, Any]]) -> str:
    """
    Uses Gemini to formulate a highly targeted query to resolve the detected contradictions.
    """
    conflict_desc = ""
    for c in conflicts:
        conflict_desc += f"\n- Subject: {c.get('subject')}\n  Clash A: {c.get('clash_a')}\n  Clash B: {c.get('clash_b')}\n"

    prompt = f"""
    You are an AI research investigator. We detected data contradictions in our retrieved sources:
    {conflict_desc}

    Formulate a single highly specific search query to find the truth, resolve these contradictions, or find consensus.
    Output only the raw search query. Do not use quotes, bullet points, or markdown.
    """

    from google import genai
    from src.config import settings
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    raw_pipeline = [
        "gemini-2.5-flash",
        "gemini-2.5-flash"
    ]
    pipeline = list(dict.fromkeys(raw_pipeline))

    for model in pipeline:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=prompt
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"[Orchestrator Warning] Tie-breaker query generation with {model} failed: {e}")

    if conflicts:
        return f"{conflicts[0].get('subject')} truth consensus"
    return state.user_query


async def scout_node_func(state: ResearchState) -> ResearchState:
    print("\n[AURA GRAPH] 🔍 Running Ingestion Scout Node...")
    return await scout.execute(state)


async def librarian_node_func(state: ResearchState) -> ResearchState:
    print("\n[AURA GRAPH] 📚 Running Librarian Cache Node...")
    return await librarian.execute(state)


async def auditor_node_func(state: ResearchState) -> ResearchState:
    print("\n[AURA GRAPH] 🔬 Running Auditor Fact Mining Node...")
    state = await auditor.execute(state)

    # 1. Run divergence gate to check for contradictions
    print("[AURA GRAPH] 🧬 Evaluating factual divergence...")
    gate_result = divergence_checker.check_for_contradictions(state)
    state.conflicts = gate_result.get("deltas", [])

    # 2. Sync triples into Neo4j
    try:
        from src.graph_writer import GraphWriter
        writer = GraphWriter()
        print("[AURA GRAPH] 💾 Syncing triples to Neo4j Graph Database...")
        await writer.write_triples_to_graph(state)
    except Exception as e:
        print(f"[AURA GRAPH Warning] Neo4j Sync bypassed or failed: {e}")

    # 3. Set routing state depending on conflicts and loopback count
    if state.conflicts and len(state.tie_breaker_queries) < 1:
        print(f"[AURA GRAPH] ⚠️ Conflicts detected! Formulating tie-breaker query...")
        tie_breaker = await generate_tie_breaker_query(state, state.conflicts)
        state.tie_breaker_queries.append(tie_breaker)
        state.active_routing_target = "loopback"
    else:
        state.active_routing_target = "synthesize"

    return state


async def synthesizer_node_func(state: ResearchState) -> ResearchState:
    print("\n[AURA GRAPH] 📄 Running Report Synthesizer Node...")
    synthesis_tiers = [
        synthesizer.model, 
        "gemini-2.5-flash",
        "gemini-2.5-flash"
    ]
    synthesis_tiers = list(dict.fromkeys(synthesis_tiers))

    for idx, fallback_model in enumerate(synthesis_tiers):
        try:
            if idx > 0:
                print(f"[AURA GRAPH] ⚠️ Primary synthesis tier overloaded. Switching to: {fallback_model}")

            synthesizer.model = fallback_model
            state = await synthesizer.execute(state)

            if state.final_report and "System Generation Error" not in state.final_report and "Generation Failure" not in state.final_report:
                break
        except Exception as tier_error:
            print(f"[AURA GRAPH] ⚠️ Synthesis tier {fallback_model} failed: {tier_error}")
            if idx == len(synthesis_tiers) - 1:
                raise tier_error
            await asyncio.sleep(2)

    return state


def route_after_auditor(state: ResearchState) -> str:
    target = getattr(state, "active_routing_target", "synthesize")
    if target == "loopback":
        print("[AURA GRAPH] 🔄 Conditional Route: Routing back to Scout Node for contradiction audit resolution.")
        return "loopback"
    else:
        print("[AURA GRAPH] 🎯 Conditional Route: Routing to Synthesizer Node.")
        return "synthesize"


# Build LangGraph Workflow
workflow = StateGraph(ResearchState)

# Register nodes
workflow.add_node("scout", scout_node_func)
workflow.add_node("librarian", librarian_node_func)
workflow.add_node("auditor", auditor_node_func)
workflow.add_node("synthesizer", synthesizer_node_func)

# Set entry point
workflow.set_entry_point("scout")

# Define edges
workflow.add_edge("scout", "librarian")
workflow.add_edge("librarian", "auditor")

# Add loopback conditional routing edge
workflow.add_conditional_edges(
    "auditor",
    route_after_auditor,
    {
        "loopback": "scout",
        "synthesize": "synthesizer"
    }
)

# Connect synthesizer to termination state
workflow.add_edge("synthesizer", END)

# Export the compiled executable graph
aura_app = workflow.compile()