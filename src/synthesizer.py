import os
import google.genai as genai
from src.state import ResearchState, BaseAgent


class SynthesizerAgent(BaseAgent):
    """
    HIGH-COGNITION RESEARCH SYNTHESIZER
    Triggered by the Orchestrator after all divergence checks pass.
    Compiles the final white-paper report matching strict citation structures.
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        super().__init__(name="Synthesizer Core", model=model)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing from the system environment!")

        self.client = genai.Client(api_key=api_key)

    async def execute(self, state: ResearchState) -> ResearchState:
        print(f"📄 [{self.name}] Synthesizing comprehensive white-paper document using {self.model}...")

        # Structure knowledge graph facts into a clean inline reading list
        graph_matrix = "\n".join([
            f"• Entity Overlap: ({t.get('subject')} -> {t.get('predicate')} -> {t.get('object')}) [Weight: {t.get('confidence', 1.0)}]"
            for t in state.knowledge_graph
        ]) if state.knowledge_graph else "No structured paths registered."

        # Format resolved conflicts to explain consensus data points
        resolved_deltas = "\n".join([
            f"Resolved Contradiction on '{c.get('subject')}': {c.get('clash_a')} VS {c.get('clash_b')}"
            for c in state.conflicts
        ]) if state.conflicts else "Zero critical structural conflicts identified by the Divergence Gate."

        # Sort documents by credibility (highest first) for proportional context extraction
        sorted_docs_for_cache = sorted(state.raw_documents, key=lambda d: d.get("credibility_score", 50), reverse=True)

        # Weight snippet length proportionally: credibility 90+ = 1500 chars, 70-89 = 900, below = 400
        cached_docs_summary = ""
        for i, doc in enumerate(sorted_docs_for_cache[:8]):
            score = doc.get("credibility_score", 50)
            if score >= 90:
                snippet_len = 1500
            elif score >= 70:
                snippet_len = 900
            else:
                snippet_len = 400
            cached_docs_summary += f"\n[Source Doc {i + 1} | Credibility: {score}%]: {doc.get('url', 'Unknown Link')}\nSnippet: {doc.get('text', '')[:snippet_len]}\n"

        # Define context_data to avoid NameError
        context_data = getattr(state, "compiled_cache", None) or cached_docs_summary

        # Sort sources by credibility (highest first) so the LLM sees the most trusted content first
        sorted_docs = sorted(state.raw_documents, key=lambda d: d.get("credibility_score", 50), reverse=True)

        # Build the available source index for the LLM to reference (sorted by credibility)
        source_index = ""
        for idx, doc in enumerate(sorted_docs):
            source_type = doc.get("source_type", "web")
            tag = "ACADEMIC" if source_type == "academic" else "WEB"
            score = doc.get("credibility_score", 50)
            source_index += f"[{idx + 1}] ({tag}, Credibility: {score}%) {doc.get('title', 'Untitled')} — {doc.get('url', '')}\n"

        synthesis_prompt = f"""
        You are a senior academic researcher publishing a definitive, peer-review-quality technical report.
        Your objective is to synthesize a comprehensive research report based ONLY on the provided context data.

        IMPORTANT FORMATTING RULES:
         - Do NOT use any emojis anywhere in the output.
         - Use formal, academic language throughout.
         - You MUST include AT LEAST 6 distinct inline citations (e.g., "[1]", "[2]", "[3]") spread across ALL sections.
         - Every factual claim, statistic, timeline, and technical detail MUST be cited using the citation keys from the SOURCE INDEX below.
         - Use citations from BOTH academic sources (marked ACADEMIC) and web sources (marked WEB) to show source diversity.
         - Do NOT cluster all citations in one paragraph. Distribute them evenly across the report.
         - Do NOT compile or generate a "References", "Bibliography", or "Citations" section at the end of your response. The system will append the official "References & Citations" section programmatically. Stop generation after Section V (Conclusions).


        ### SOURCE INDEX (use these citation keys):
        {source_index}

        ### TOPIC FRAMEWORK:
        {state.user_query}

        ### PROVIDED CONTEXT DATA:
        {context_data}

        ### KNOWLEDGE GRAPH FACTS:
        {graph_matrix}

        ### RESOLVED CONTRADICTIONS:
        {resolved_deltas}

        ### MANDATORY LAYOUT SPECIFICATIONS:
        You must output your response in Markdown using the following structure exactly. Do not use generic summary text. Adapt the terminology cleanly to match the user's target topic framework.

        # AuRA Research Report: [Insert Topic Title Dynamically]

        ### System Metadata and Graph Metrics
        * **Ingestion Pipeline Status:** Verification Concluded Successfully
        * **Knowledge Graph Density:** {len(state.knowledge_graph)} Active Fact Triples Mapped
        * **Sources Analyzed:** {len(state.raw_documents)} documents across academic, government, and industry databases
        * **Adversarial Audit State:** Divergence Threshold Active (0.20 Target)
        * **Consensus Status:** {"Conflicts Resolved" if state.conflicts else "High Fidelity"}

        ---

        ## I. Executive Summary
        [Provide a formal executive overview synthesizing the key findings from the multi-agent research pipeline. You MUST include at least 2 inline citations in this section.]

        ---

        ## II. Chronology and Key Developments
        [Break down the key timeline milestones, structural movements, or operational developments found in the data as concrete points. You MUST include at least 2 inline citations in this section.]

        ---

        ## III. Technical Analysis
        [Select the most critical conceptual axis of the topic and provide an advanced analytical breakdown. Use blockquotes for architectural or technical highlights. You MUST include at least 2 inline citations in this section.]

        ---

        ## IV. Cross-Verification and Consensus Audit
        The system executed multiple cross-verification checks across independent data clusters. Detail the alignment or lack of conflicts found within the source material. Highlight any resolved contradictions using the inline citation keys.

        ---

        ## V. Conclusions
        [Provide final authoritative conclusions regarding long-term trends and implications.]
        """

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=synthesis_prompt
            )

            if response.text:
                report_body = response.text.strip()

                # Programmatically compile references section with source diversity badges
                references_section = "\n\n---\n\n## VI. References & Citations\n"

                # Separate academic and web sources
                academic_refs = []
                web_refs = []

                for idx, doc in enumerate(sorted_docs):
                    url = doc.get("url", "")
                    if not url or "In-Memory Cache Matrix" in url:
                        continue

                    citation_key = doc.get("citation_key", f"[{idx + 1}]")
                    title = doc.get("title", "Untitled Reference")
                    score = doc.get("credibility_score", 50)
                    source_type = doc.get("source_type", "web")

                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    if domain.startswith("www."):
                        domain = domain[4:]

                    # Classify source type for badge
                    if source_type == "academic":
                        badge = "🎓 Academic"
                        academic_citation = doc.get("academic_citation", "")
                        ref_line = f"{citation_key} {badge} — **{title}**  \n"
                        if academic_citation:
                            ref_line += f"*{academic_citation}*  \n"
                        ref_line += f"*Source:* [{domain}]({url}) | *Reliability Score:* **{score}%**  \n\n"
                        academic_refs.append((score, ref_line))
                    else:
                        if domain.endswith(".gov") or domain.endswith(".gov.uk"):
                            badge = "🏛️ Government"
                        elif domain.endswith(".edu") or domain.endswith(".ac.uk"):
                            badge = "🎓 Academic"
                        elif any(x in domain for x in ["reuters", "bloomberg", "bbc", "nytimes", "guardian"]):
                            badge = "📰 News"
                        else:
                            badge = "🏢 Industry / Web"

                        ref_line = f"{citation_key} {badge} — **{title}**  \n*Source:* [{domain}]({url}) | *Reliability Score:* **{score}%**  \n\n"
                        web_refs.append((score, ref_line))

                # Sort both lists descending by credibility score
                academic_refs.sort(key=lambda x: x[0], reverse=True)
                web_refs.sort(key=lambda x: x[0], reverse=True)

                if academic_refs:
                    references_section += "### Academic Sources\n"
                    for _, ref in academic_refs:
                        references_section += ref

                if web_refs:
                    references_section += "### Web & Industry Sources\n"
                    for _, ref in web_refs:
                        references_section += ref

                if academic_refs or web_refs:
                    state.final_report = report_body + references_section
                else:
                    state.final_report = report_body

                print(
                    f"✅ [{self.name}] Final white-paper report synthesized perfectly ({len(state.final_report)} characters).")
            else:
                state.final_report = "⚠️ System Error: Synthesizer core returned an empty response layout."
        except Exception as e:
            print(f"❌ [{self.name}] Error occurred during final document generation: {str(e)}")
            state.final_report = f"### Generation Failure\nAn exception blocked the Synthesizer Agent: {str(e)}"

        return state
