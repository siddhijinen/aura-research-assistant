import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from src.state import ResearchState
from src.config import settings


class ClashingPair(BaseModel):
    """
    Represents a specific semantic clash between two sources.
    """
    subject: str = Field(description="The specific concept or topic under conflict, e.g. 'Timeline for Quantum Threat'")
    clash_a: str = Field(description="Asserted claim from Source A, formatted as: '[Source Name](URL): claim text'. Include the source URL as a markdown link if available.")
    clash_b: str = Field(description="Asserted claim from Source B, formatted as: '[Source Name](URL): claim text'. Include the source URL as a markdown link if available.")
    source_a_url: str = Field(default="", description="Direct URL for the Source A document, if available.")
    source_b_url: str = Field(default="", description="Direct URL for the Source B document, if available.")


class ConflictDetectionPayload(BaseModel):
    """
    Strict payload matching structural audit checks.
    """
    conflicts: List[ClashingPair]


class DivergenceGate:
    """
    SECURITY AUDITING LAYER: Semantic Divergence Gate
    Reviews extracted triples using high-cognition auditing to identify conflicting facts.
    """

    def __init__(self, conflict_threshold: float = 0.20):
        self.conflict_threshold = conflict_threshold
        # Initialize native Client using the settings key
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def check_for_contradictions(self, state: ResearchState) -> Dict[str, Any]:
        """
        Analyzes the knowledge graph triples and uses Gemini structured outputs to find semantic contradictions.
        """
        triples = state.knowledge_graph
        if not triples or len(triples) < 2:
            return {"divergence_detected": False, "conflict_score": 0.0, "deltas": []}

        # Format triples for LLM inspection
        triples_str = ""
        for idx, t in enumerate(triples):
            source_info = t.get("source_citation", f"Reference {idx + 1}")
            triples_str += f"- [{source_info}]: ({t['subject']}) --[{t['predicate']}]--> ({t['object']})\n"

        prompt = f"""
        You are a data validation auditor. Review the following list of extracted factual triples and identify any semantic contradictions, timeline conflicts, version mismatches, or opposing claims on the same concepts.

        When reporting conflicts, format clash_a and clash_b as Markdown hyperlinks using the source URL:
        Example format: "[Source Title](https://example.com): claim text here"
        If no URL is available, just use the source name.

        ### EXTRACTED FACTUAL TRIPLES:
        {triples_str}
        """

        raw_pipeline = [
            "gemini-2.5-flash",
            "gemini-2.5-flash"
        ]
        response = None
        last_error = None

        for model in raw_pipeline:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=ConflictDetectionPayload
                    )
                )
                break
            except Exception as e:
                print(f"[DivergenceGate Warning] Attempt with {model} failed: {e}")
                last_error = e

        if not response:
            print(f"[DivergenceGate Error] All model attempts in pipeline failed. Last error: {last_error}")
            return {"divergence_detected": False, "conflict_score": 0.0, "deltas": []}

        deltas = []
        try:
            if response and response.parsed:
                payload: ConflictDetectionPayload = response.parsed
                for conflict in payload.conflicts:
                    deltas.append({
                        "subject": conflict.subject,
                        "clash_a": conflict.clash_a,
                        "clash_b": conflict.clash_b,
                        "source_a_url": conflict.source_a_url or "",
                        "source_b_url": conflict.source_b_url or "",
                    })
        except Exception as e:
            print(f"[DivergenceGate Error] Failed to parse response payload: {e}")

        # Calculate conflict percentage
        conflict_score = len(deltas) / len(triples) if triples else 0.0
        return {
            "divergence_detected": len(deltas) > 0,
            "conflict_score": conflict_score,
            "deltas": deltas
        }