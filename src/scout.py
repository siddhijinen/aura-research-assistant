import os
import asyncio
from typing import List, Dict, Any
from google import genai
from google.genai import types
from tavily import AsyncTavilyClient
from src.state import BaseAgent, ResearchState
from src.config import settings


class ScoutAgent(BaseAgent):
    """
    The Ingestion Scout. Uses clean cascading Flash architectures to plan
    structural search optimization queries, then executes concurrent web lookups
    using the Tavily Async engine.
    """

    # FIXED: Added model argument to match orchestrator constructor overrides
    def __init__(self, model: str = "gemini-2.5-flash"):
        super().__init__(name="ScoutAgent", model=model)
        # Initialize native Google GenAI SDK client
        self.ai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Initialize Tavily Async Client
        self.search_client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)

    async def _generate_search_queries(self, user_query: str) -> List[str]:
        """
        Uses cascading failover protections to prevent quota exhaustion crashes.
        """
        prompt = f"""
        You are an advanced search optimization engine for a research assistant.
        Given the following user research request, generate exactly 5 distinct,
        highly optimized search queries. The queries MUST cover diverse source types:
        - At least 1 query targeting academic research papers or journal articles (include terms like "research paper", "study", "journal", "arxiv", or "IEEE")
        - At least 1 query targeting government or standards body publications (include terms like "NIST", "report", "whitepaper", or "regulation")
        - At least 1 query targeting industry analysis or technical documentation
        - The remaining queries should target different angles of the topic

        User Request: "{user_query}"

        Output exactly 5 lines, with one pure search query per line. Do not include markdown formatting, bullet points, or numbering.
        """

        # FIXED: Dynamically deduplicate pipeline to prevent repeating endpoints
        # FIXED: Wiped out 'gemini-3-flash' and legacy elements.
        # Using the official production-ready API string name key.
        raw_pipeline = [
            self.model, 
            "gemini-2.5-flash",
            "gemini-2.5-flash"
        ]
        scout_pipeline = list(dict.fromkeys(raw_pipeline))
        response = None

        from src.config import execute_with_retry
        for idx, target_model in enumerate(scout_pipeline):
            try:
                if idx > 0:
                    print(f"⚠️ [Scout] Tier {scout_pipeline[idx - 1]} limited. Falling back to: {target_model}...")

                response = await asyncio.to_thread(
                    execute_with_retry,
                    self.ai_client.models.generate_content,
                    model=target_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=300
                    )
                )
                break
            except Exception as e:
                error_msg = str(e).upper()
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if idx < len(scout_pipeline) - 1:
                        continue
                raise e

        if not response or not response.text:
            print(f"❌ [Scout Warning] All LLM tiers exhausted. Defaulting directly to fallback user string.")
            return [user_query]

        queries = [line.strip() for line in response.text.strip().split("\n") if line.strip()]
        if not queries:
            return [user_query]
        return queries[:5]

    async def _execute_single_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes an asynchronous query against Tavily searching for raw markdown.
        """
        try:
            response = await self.search_client.search(
                query=query,
                search_depth="advanced",
                max_results=4,
                include_raw_content=True
            )

            results = []
            for raw in response.get("results", []):
                results.append({
                    "title": raw.get("title", "Untitled Source"),
                    "url": raw.get("url", ""),
                    "content": raw.get("raw_content") or raw.get("content") or ""
                })
            return results
        except Exception as e:
            print(f"  [Scout Warning] Search execution failed for '{query}': {e}")
            return []

    async def execute(self, state: ResearchState) -> ResearchState:
        # Check if we have an active tie-breaker query in loopback mode
        target_query = state.user_query
        is_loopback = False
        if getattr(state, "tie_breaker_queries", None):
            target_query = state.tie_breaker_queries[-1]
            is_loopback = True
            print(f"🔄 [Scout] Loopback active. Targeting resolving query: '{target_query}'")
        else:
            print(f"🔍 [Scout] Optimizing query footprint for: '{state.user_query}'")

        # 1. Generate optimized queries across our resilient infrastructure
        search_queries = await self._generate_search_queries(target_query)
        print(f"🔍 [Scout] Dispatched targets: {search_queries}")

        # 2. Concurrently execute web queries via asyncio tasks
        tasks = [self._execute_single_search(q) for q in search_queries]
        search_payloads = await asyncio.gather(*tasks)

        # 3. Concurrently fetch academic papers from arXiv + Semantic Scholar
        from src.scholar import fetch_academic_papers
        academic_papers = await fetch_academic_papers(target_query, max_per_source=3)

        # 4. Flatten and process incoming web documents
        deduped_docs: Dict[str, Dict[str, Any]] = {}
        for payload in search_payloads:
            for doc in payload:
                if doc["url"] and doc["url"] not in deduped_docs:
                    deduped_docs[doc["url"]] = doc

        from src.credibility import compute_credibility_score
        raw_docs_list = list(deduped_docs.values())
        for idx, doc in enumerate(raw_docs_list):
            doc["citation_key"] = f"[{idx + 1}]"
            doc["source_type"] = doc.get("source_type", "web")
            doc["credibility_score"] = compute_credibility_score(doc["url"], doc.get("title", ""))

        # 5. Merge academic papers into the document list
        offset = len(raw_docs_list)
        for paper in academic_papers:
            if paper["url"] and paper["url"] not in deduped_docs:
                paper["citation_key"] = f"[{offset + 1}]"
                paper["credibility_score"] = 93  # Academic sources get high credibility
                raw_docs_list.append(paper)
                deduped_docs[paper["url"]] = paper
                offset += 1

        print(f"🎓 [Scout] Academic sources injected: {len(academic_papers)} papers merged into pipeline.")

        # 6. Merge results if loopback, otherwise assign directly
        if is_loopback and getattr(state, "raw_documents", None):
            existing_docs = {doc["url"]: doc for doc in state.raw_documents if "url" in doc}
            merged_docs = list(existing_docs.values())
            merge_offset = len(merged_docs)
            for idx, doc in enumerate(raw_docs_list):
                if doc["url"] not in existing_docs:
                    doc["citation_key"] = f"[{merge_offset + 1}]"
                    merged_docs.append(doc)
                    merge_offset += 1
            state.raw_documents = merged_docs
        else:
            state.raw_documents = raw_docs_list

        print(f"✅ [Scout] Ingestion sequence complete. Active document tree size: {len(state.raw_documents)}.")

        return state