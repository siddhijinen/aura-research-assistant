import os
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from src.state import BaseAgent, ResearchState
from src.config import settings


# --- STAGE 1: DEFINE STRUCTURAL OUTPUT GRAPH CONTRACTS ---
class FactTriple(BaseModel):
    """
    Represents a clean, atomic cross-verified factual relationship triple
    optimized for Knowledge Graph loading.
    """
    subject: str = Field(description="The core entity, node, or concept (Noun). e.g., 'NIST'")
    predicate: str = Field(description="The relationship or action directional vector (Verb). e.g., 'STANDARDIZES'")
    object: str = Field(description="The target entity, property value, or state (Noun). e.g., 'Kyber'")
    confidence: float = Field(
        description="Confidence extraction score bounded between 0.0 and 1.0 based on explicit source convergence.")
    source_citation: str = Field(
        description="Strict anchor identifier mapping back to the title or URL of the provided context document.")


class FactExtractionPayload(BaseModel):
    """
    Strict root layout containing an isolated array sequence of extracted factual triples.
    """
    triples: List[FactTriple]


# --- STAGE 2: BUILD AGENT ORCHESTRATION LAYER ---
class AuditorAgent(BaseAgent):  # Simplified mapping to match BaseAgent setup cleanly
    """
    AGENT: AuditorAgent (Verification Layer)

    Reads from the compiled text cache stream optimized by the Librarian and
    extracts clear semantic triples using Gemini Structured Outputs.
    """

    # FIXED: Accept model argument parameter string to prevent TypeError initialization crashes
    def __init__(self, model: str = "gemini-2.5-flash"):
        super().__init__(name="AuditorAgent", model=model)
        self.ai_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _call_gemini_raw(self, prompt: str, target_model: str) -> Any:
        """
        Executes structural query generation content requests.
        """
        return self.ai_client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=FactExtractionPayload,
            )
        )

    async def execute(self, state: ResearchState) -> ResearchState:
        print(f"🔬 [{self.name}] Initiating fact mining sequence across document index context...")

        # Extract data cleanly from state tracking layers, prioritizing compiled_cache
        context_data = ""
        if getattr(state, "compiled_cache", None):
            context_data = state.compiled_cache
        elif hasattr(state, 'raw_documents') and state.raw_documents:
            context_data = "\n\n".join([doc.get("text") or doc.get("content") or "" for doc in state.raw_documents])

        if not context_data.strip():
            print(f"⚠️ [{self.name}] No valid document content found in state registry. Skipping mining cycle.")
            state.knowledge_graph = []
            return state

        prompt = f"""
        You are a senior data extraction engineer specializing in Knowledge Graph engineering.
        Your task is to analyze the following provided research documents and mine definitive, 
        factual relationships as atomic subject-predicate-object triples.

        Focus areas: Timelines, technical specification standards, vendor transitions, or protocol versions.

        Guidelines:
        1. Keep entity names uniform and clean. Do not include markdown or wrapping syntax inside property fields.
        2. Extracted predicates must reflect strict directional relationships (use active verbs, alphanumeric characters, and spaces only).
        3. Only extract values explicitly supported by the text.

        ### RESEARCH DOCUMENTS CONTEXT:
        {context_data}
        """

        response = None

        raw_pipeline = [
            self.model, 
            "gemini-2.5-flash",
            "gemini-2.5-flash"
        ]
        model_pipeline = list(dict.fromkeys(raw_pipeline))

        from src.config import execute_with_retry
        for idx, target_model in enumerate(model_pipeline):
            try:
                if idx > 0:
                    print(
                        f"⚠️ [{self.name}] Cluster busy or limited. Switching execution tier to target model: {target_model}...")

                # Non-blocking async execution wrapper with backoff retries
                response = await asyncio.to_thread(execute_with_retry, self._call_gemini_raw, prompt, target_model)

                if response and (response.text or hasattr(response, 'parsed')):
                    break

            except Exception as e:
                error_msg = str(e).upper()

                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "503" in error_msg or "UNAVAILABLE" in error_msg:
                    print(f"⏳ [{self.name}] Tier {target_model} failed all retries due to quota limits.")
                    if idx < len(model_pipeline) - 1:
                        continue
                raise e

        if not response:
            print(
                f"❌ [{self.name} Failure] All Gemini generation tiers are currently experiencing high demand. Aborting extraction frame.")
            state.knowledge_graph = []
            return state

        try:
            # Access pre-parsed Pydantic instances natively through the modern SDK framework
            parsed_payload: FactExtractionPayload = response.parsed

            if not parsed_payload or not parsed_payload.triples:
                print(f"⚠️ [{self.name}] Model returned valid JSON, but array block contained 0 triples.")
                state.knowledge_graph = []
                return state

            extracted_list = []
            for item in parsed_payload.triples:
                extracted_list.append(item.model_dump())

            state.knowledge_graph = extracted_list
            print(
                f"✅ [{self.name}] Fact extraction complete! Safely mined {len(state.knowledge_graph)} factual triples.")

            for entry in state.knowledge_graph[:3]:
                print(f"  -> Triple Found: ({entry['subject']}) --[{entry['predicate']}]--> ({entry['object']})")

        except Exception as e:
            print(f"❌ [{self.name} Failure] Failed to parse structured output graph format: {e}")
            state.knowledge_graph = []

        return state