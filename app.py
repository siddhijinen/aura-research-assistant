import streamlit as st
import asyncio
import time
import json
import os
import csv
import io
import streamlit.components.v1 as components
from pydantic import BaseModel, Field
from typing import List, Optional
from src.state import ResearchState
from src.orchestrator import aura_app
from google import genai
from google.genai import types
from src.config import settings, execute_with_retry

# Enforce clean, responsive page constraints
st.set_page_config(
    page_title="AuRA // Your Autonomous Research Assistant",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Academic UI CSS Injection
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Lora:ital,wght@0,400;0,500;1,400&family=Montserrat:wght@300;400;500;600&display=swap');
        
        /* Set page background to clean academic white */
        .stApp {
            background-color: #FFFFFF !important;
            color: #1A1A1A !important;
        }
        
        /* Global typography */
        html, body, [class*="css"] {
            font-family: 'Montserrat', sans-serif;
        }
        
        /* Sidebar layout styling */
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E3DED2 !important;
        }
        
        /* Paper Container */
        .paper-theme div[data-testid="stVerticalBlockBorder"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E3DED2 !important;
            border-radius: 4px !important;
            padding: 45px 55px !important;
            box-shadow: 0px 4px 25px rgba(0, 0, 0, 0.03) !important;
            margin-top: 15px !important;
            margin-bottom: 25px !important;
        }
        
        /* Lora serif font styling for readability */
        .paper-theme div[data-testid="stVerticalBlockBorder"] div[data-testid="stMarkdownContainer"] {
            font-family: 'Lora', serif !important;
            font-size: 16.5px !important;
            line-height: 1.85 !important;
            color: #2C2C2C !important;
        }
        
        /* Academic Header font layout styling */
        .paper-theme div[data-testid="stVerticalBlockBorder"] h1, 
        .paper-theme div[data-testid="stVerticalBlockBorder"] h2, 
        .paper-theme div[data-testid="stVerticalBlockBorder"] h3, 
        .paper-theme div[data-testid="stVerticalBlockBorder"] h4 {
            font-family: 'Cinzel', serif !important;
            font-weight: 600 !important;
            color: #111111 !important;
            margin-top: 30px !important;
            margin-bottom: 15px !important;
            letter-spacing: 0.5px;
        }
        
        .paper-theme div[data-testid="stVerticalBlockBorder"] h1 {
            font-size: 2.2em !important;
            text-align: center;
            border-bottom: 1px double #CCCCCC;
            padding-bottom: 15px;
            margin-bottom: 35px !important;
        }
        
        .paper-theme div[data-testid="stVerticalBlockBorder"] h2 {
            font-size: 1.45em !important;
            border-bottom: 1px solid #E3DED2;
            padding-bottom: 6px;
        }
        
        .paper-theme div[data-testid="stVerticalBlockBorder"] hr {
            border-top: 1px solid #E3DED2 !important;
            margin: 25px 0 !important;
        }
        
        /* Contradiction Dashboard Card styles */
        .conflict-ledger {
            background-color: #FFF5F5 !important;
            border-left: 4px solid #D9534F !important;
            border-top: 1px solid #FADBD8 !important;
            border-right: 1px solid #FADBD8 !important;
            border-bottom: 1px solid #FADBD8 !important;
            border-radius: 4px;
            padding: 16px;
            margin-bottom: 15px;
        }
        
        .conflict-title {
            color: #C0392B !important;
            font-weight: 600 !important;
            font-size: 13.5px !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        
        .conflict-detail {
            font-size: 13px !important;
            color: #444444 !important;
            line-height: 1.55 !important;
        }
        
        /* Supplementary section preview */
        .supplement-preview {
            background-color: #F0F7FF !important;
            border-left: 4px solid #1E88E5 !important;
            border-top: 1px solid #BBDEFB !important;
            border-right: 1px solid #BBDEFB !important;
            border-bottom: 1px solid #BBDEFB !important;
            border-radius: 4px;
            padding: 18px 22px;
            margin: 16px 0;
            font-family: 'Lora', serif;
            font-size: 14.5px;
            line-height: 1.75;
            color: #2C2C2C;
        }
        
        .supplement-label {
            font-family: 'Montserrat', sans-serif;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #1565C0;
            margin-bottom: 10px;
        }

        /* Minimalist Input Buttons */
        div.stButton > button {
            background-color: #FFFFFF !important;
            color: #1A1A1A !important;
            border: 1px solid #E3DED2 !important;
            border-radius: 4px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-size: 13.5px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease;
        }
        
        div.stButton > button:hover {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
            border-color: #1A1A1A !important;
        }
        
        div.stButton > button[type="primary"] {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
            border-color: #1A1A1A !important;
        }
        
        div.stButton > button[type="primary"]:hover {
            background-color: #333333 !important;
            color: #FFFFFF !important;
            border-color: #333333 !important;
        }
    </style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────────

class QueryValidation(BaseModel):
    """
    Structured response mapping user query validations.
    """
    is_valid: bool = Field(description="False if the user input is gibberish, letters mash, or purely non-sensical noise.")
    is_too_vague: bool = Field(description="True if the query is a single broad term and lacks research focus.")
    refined_query: str = Field(description="Formulated specific research query, populated only if is_valid is True and is_too_vague is False.")
    response: str = Field(description="A friendly, technical response greeting the user, asking clarifying questions, or confirming the research plan.")


class InquiryResult(BaseModel):
    """
    Structured output for the cache-first inquiry step.
    """
    found_in_cache: bool = Field(description="True if the report data contains sufficient information to answer the question confidently.")
    answer: str = Field(description="The answer if found_in_cache is True, otherwise an empty string.")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def validate_and_refine_query(user_message: str, chat_history: list) -> QueryValidation:
    """
    Validates user prompt for noise/vagueness using Gemini 2.5 Flash.
    """
    history_str = ""
    for role, text in chat_history:
        history_str += f"{role.upper()}: {text}\n"

    prompt = f"""
    You are AuRA Guide, an interactive research onboarding assistant. Your job is to help the user refine their research topic.
    Verify that the user's latest input is a valid research target.

    Rules:
    1. If the input is gibberish or nonsensical (e.g. "asdf", "helloooo"), set is_valid=False and ask the user to provide a valid topic.
    2. If the input is too vague or broad (e.g. "artificial intelligence", "quantum"), set is_too_vague=True. In your response, suggest 2-3 specific research angles formatted as a NUMBERED LIST with each option on its OWN LINE. After the list, explicitly tell the user: "Feel free to pick one of the above, or describe your own specific angle — I'll refine it for you."
    3. If the input is specific and valid, set is_valid=True and is_too_vague=False. Generate a highly optimized, technical "refined_query" that the research agents can use to find sources.
    4. If the user picks or elaborates on a previously suggested option, treat it as valid and generate the refined_query.

    ### CONVERSATION HISTORY:
    {history_str}

    ### USER LATEST INPUT:
    {user_message}
    """

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = execute_with_retry(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=QueryValidation,
            )
        )
        if res and res.parsed:
            return res.parsed
    except Exception as e:
        print(f"[Onboarding Warning] Failed to validate query: {e}")
        
    return QueryValidation(
        is_valid=True,
        is_too_vague=False,
        refined_query=user_message,
        response=f"I encountered a temporary connection bottleneck. Let's proceed directly with your query: '{user_message}'"
    )


def build_triples_csv(kg_data: list) -> str:
    """Serializes knowledge graph triples to CSV string."""
    output = io.StringIO()
    fieldnames = ["subject", "predicate", "object", "confidence", "source_citation"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for triple in kg_data:
        writer.writerow({
            "subject": triple.get("subject", ""),
            "predicate": triple.get("predicate", ""),
            "object": triple.get("object", ""),
            "confidence": triple.get("confidence", 1.0),
            "source_citation": triple.get("source_citation", ""),
        })
    return output.getvalue()


def render_interactive_graph(kg_triples: list, search_term: str = "", visible_types: Optional[List[str]] = None) -> str:
    """
    Builds an interactive vis.js force-directed network graph string.
    Categorizes nodes visually: Sources (blue), Timelines/Data (yellow), Entities (green).
    Supports search highlighting and type-based filtering.
    """
    if visible_types is None:
        visible_types = ["Sources", "DataPoints", "Entities"]

    nodes = {}
    edges = []

    def get_node_category(name):
        name_lower = name.lower()
        if any(x in name_lower for x in ["http", ".com", ".org", ".edu", "report", "pdf", "citation", "source"]):
            return "Sources"
        elif any(char.isdigit() for char in name_lower):
            return "DataPoints"
        else:
            return "Entities"

    def get_node_style(category):
        if category == "Sources":
            return "#E1F5FE", "#0288D1"
        elif category == "DataPoints":
            return "#FFF9C4", "#FBC02D"
        else:
            return "#E8F5E9", "#388E3C"

    def confidence_to_color(conf: float) -> str:
        """Maps confidence 0.0-1.0 to a red-yellow-green gradient."""
        conf = max(0.0, min(1.0, conf))
        if conf < 0.5:
            r, g = 220, int(100 + 155 * (conf / 0.5))
        else:
            r, g = int(220 - 180 * ((conf - 0.5) / 0.5)), 200
        return f"rgb({r},{g},60)"

    for triple in kg_triples:
        sub = triple.get("subject", "").strip()
        obj = triple.get("object", "").strip()
        pred = triple.get("predicate", "").strip()
        conf = triple.get("confidence", 1.0)

        sub_cat = get_node_category(sub)
        obj_cat = get_node_category(obj)

        # Filter by visible type
        if sub_cat not in visible_types or obj_cat not in visible_types:
            continue

        if sub and sub not in nodes:
            fill, border = get_node_style(sub_cat)
            nodes[sub] = {
                "id": sub,
                "label": sub,
                "group": sub_cat,
                "color": {"background": fill, "border": border, "highlight": {"background": fill, "border": border}},
                "shape": "box"
            }
        if obj and obj not in nodes:
            fill, border = get_node_style(obj_cat)
            nodes[obj] = {
                "id": obj,
                "label": obj,
                "group": obj_cat,
                "color": {"background": fill, "border": border, "highlight": {"background": fill, "border": border}},
                "shape": "box"
            }

        if sub and obj:
            edge_color = confidence_to_color(conf)
            edges.append({
                "from": sub,
                "to": obj,
                "label": pred.upper().replace("_", " "),
                "title": f"Confidence: {conf:.0%}",
                "arrows": "to",
                "font": {"size": 8, "align": "middle", "face": "Courier New"},
                "color": {"color": edge_color, "highlight": "#1A1A1A"},
                "width": max(1, conf * 3)
            })

    nodes_json = json.dumps(list(nodes.values()))
    edges_json = json.dumps(edges)
    search_term_json = json.dumps(search_term.lower().strip())

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #FFFFFF;
            }}
            #mynetwork {{
                width: 100%;
                height: 100%;
                background-color: #FFFFFF;
                font-family: 'Montserrat', sans-serif;
            }}
            #fs-btn {{
                position: absolute;
                top: 10px;
                right: 12px;
                z-index: 999;
                background: #1A1A1A;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-family: 'Montserrat', sans-serif;
                cursor: pointer;
                letter-spacing: 0.5px;
            }}
            #fs-btn:hover {{
                background: #444444;
            }}
            #node-count {{
                position: absolute;
                bottom: 10px;
                left: 12px;
                z-index: 999;
                font-family: 'Montserrat', sans-serif;
                font-size: 11px;
                color: #888888;
                letter-spacing: 0.3px;
            }}
        </style>
    </head>
    <body>
        <div id="mynetwork"></div>
        <button id="fs-btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
        <div id="node-count"></div>
        <script type="text/javascript">
            var searchTerm = {search_term_json};

            function toggleFullscreen() {{
                var el = document.documentElement;
                if (!document.fullscreenElement) {{
                    el.requestFullscreen().catch(function(err) {{
                        alert('Fullscreen error: ' + err.message);
                    }});
                    document.getElementById('fs-btn').textContent = '✕ Exit Fullscreen';
                }} else {{
                    document.exitFullscreen();
                    document.getElementById('fs-btn').textContent = '⛶ Fullscreen';
                }}
            }}
            document.addEventListener('fullscreenchange', function() {{
                if (!document.fullscreenElement) {{
                    document.getElementById('fs-btn').textContent = '⛶ Fullscreen';
                }}
            }});

            var allNodes = {nodes_json};
            var allEdges = {edges_json};

            // Apply search highlighting: matching nodes get a golden border + bold font
            if (searchTerm) {{
                allNodes = allNodes.map(function(n) {{
                    var lbl = (n.label || '').toLowerCase();
                    if (lbl.includes(searchTerm)) {{
                        return Object.assign({{}}, n, {{
                            borderWidth: 3.5,
                            color: Object.assign({{}}, n.color, {{ border: '#F59E0B', highlight: {{ border: '#F59E0B', background: n.color.background }} }}),
                            font: {{ size: 13, bold: true, color: '#111111', face: 'Montserrat' }},
                            shadow: {{ enabled: true, color: 'rgba(245,158,11,0.35)', size: 8, x: 0, y: 0 }}
                        }});
                    }} else {{
                        // Dim non-matching nodes
                        return Object.assign({{}}, n, {{
                            opacity: 0.25,
                            font: {{ size: 10, color: '#AAAAAA', face: 'Montserrat' }}
                        }});
                    }}
                }});
            }}

            var nodes = new vis.DataSet(allNodes);
            var edges = new vis.DataSet(allEdges);

            var container = document.getElementById('mynetwork');
            var data = {{
                nodes: nodes,
                edges: edges
            }};
            var options = {{
                nodes: {{
                    shape: 'box',
                    margin: 8,
                    font: {{
                        size: 11,
                        face: 'Montserrat',
                        color: '#222222'
                    }},
                    borderWidth: 1.5,
                    shadow: {{
                        enabled: true,
                        color: 'rgba(0,0,0,0.05)',
                        size: 3,
                        x: 1,
                        y: 1
                    }}
                }},
                edges: {{
                    smooth: {{
                        type: 'cubicBezier',
                        forceDirection: 'none',
                        roundness: 0.3
                    }},
                    font: {{
                        size: 8,
                        strokeWidth: 2,
                        strokeColor: '#ffffff'
                    }}
                }},
                physics: {{
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {{
                        gravitationalConstant: -35,
                        centralGravity: 0.01,
                        springLength: 100,
                        springConstant: 0.08
                    }},
                    stabilization: {{
                        enabled: true,
                        iterations: 120
                    }}
                }}
            }};
            var network = new vis.Network(container, data, options);

            // Update node count label
            document.getElementById('node-count').textContent =
                allNodes.length + ' nodes · ' + allEdges.length + ' edges';
        </script>
    </body>
    </html>
    """
    return html_content


async def _tavily_quick_search(question: str, tavily_api_key: str) -> list:
    """Lightweight Tavily search for the inquiry fallback (basic depth, 3 results)."""
    from tavily import AsyncTavilyClient
    client = AsyncTavilyClient(api_key=tavily_api_key)
    try:
        result = await client.search(
            query=question,
            search_depth="basic",
            max_results=3,
            include_answer=True
        )
        return result.get("results", [])
    except Exception as e:
        print(f"[Inquiry/Tavily] Quick search failed: {e}")
        return []


def inquire_with_cache(question: str, report_data: str) -> InquiryResult:
    """Phase 1: Try to answer the question from the cached report using structured output."""
    prompt = f"""
You are an academic research assistant. A user is asking a follow-up question about a research report.
Determine if the report provides enough information to answer confidently.

RESEARCH REPORT:
{report_data}

USER QUESTION:
{question}

If the report contains sufficient information to answer the question, set found_in_cache=True and provide a concise, direct answer.
If the question asks about something NOT covered in the report (e.g., different topics, events after the report's scope, external data), set found_in_cache=False and leave answer as an empty string.
"""
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = execute_with_retry(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=InquiryResult,
            )
        )
        if res and res.parsed:
            return res.parsed
    except Exception as e:
        print(f"[Inquiry/Cache] Failed: {e}")
    return InquiryResult(found_in_cache=False, answer="")


def synthesize_supplement(question: str, search_results: list) -> str:
    """Synthesizes a short supplementary research note from Tavily results."""
    snippets = "\n\n".join([
        f"Source: {r.get('url', 'Unknown')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')[:600]}"
        for r in search_results
    ])
    prompt = f"""
You are a research synthesizer. Based on the web sources below, write a short, factual supplementary research note
answering the user's question. Format it as a proper markdown section with:
- A heading (e.g. ## Supplementary Note: <topic>)
- 2-4 informative paragraphs
- A brief References subsection listing the sources used

Keep the tone academic and concise. Do not pad with filler text.

USER QUESTION:
{question}

WEB SOURCES:
{snippets}
"""
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = execute_with_retry(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        if res and res.text:
            return res.text.strip()
    except Exception as e:
        print(f"[Inquiry/Supplement] Failed: {e}")
    return ""


def embed_supplement_into_report(report_data: str, supplement: str) -> str:
    """Calls Gemini to seamlessly integrate the supplementary note into the existing report."""
    prompt = f"""
You are a technical editor tasked with integrating new supplementary research into an existing report.

EXISTING REPORT:
{report_data}

SUPPLEMENTARY RESEARCH NOTE TO INTEGRATE:
{supplement}

Instructions:
- Identify the most appropriate section in the existing report where this new information belongs.
- Integrate the content naturally, preserving the existing report's voice, structure, and citation style.
- Do NOT simply append the note at the end. Weave it into the correct section.
- Maintain the existing report's heading structure.
- Return the COMPLETE updated report with the new content seamlessly embedded.
- Preserve all existing content — do not remove or shorten any original sections.
- If the new information significantly expands or alters the scope of the report, edit the main title (the main # header) of the report to reflect this broader scope if necessary.
"""
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = execute_with_retry(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        if res and res.text:
            return res.text.strip()
    except Exception as e:
        print(f"[Inquiry/Embed] Failed: {e}")
    return report_data


def save_keys_to_dotenv(gemini_key: str, tavily_key: str, scholar_key: str):
    """
    Saves/updates the API keys in the local .env file.
    Creates the .env file if it doesn't exist.
    """
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[Save Keys] Error reading existing .env: {e}")

    key_map = {
        "GEMINI_API_KEY": gemini_key.strip(),
        "TAVILY_API_KEY": tavily_key.strip(),
        "SEMANTIC_SCHOLAR_API_KEY": scholar_key.strip(),
    }
    
    updated_keys = set()
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            try:
                k, v = stripped.split("=", 1)
                k = k.strip()
                if k in key_map:
                    new_lines.append(f"{k}={key_map[k]}\n")
                    updated_keys.add(k)
                    continue
            except Exception:
                pass
        new_lines.append(line)

    for k, v in key_map.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(dotenv_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[Save Keys] Error writing .env: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

if "cached_state" not in st.session_state:
    st.session_state.cached_state = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        ("assistant", "Hello! I am AuRA Guide, your research onboarding assistant. What topic or technical question would you like to investigate today?")
    ]
if "refined_query" not in st.session_state:
    st.session_state.refined_query = None
if "interactive_history" not in st.session_state:
    st.session_state.interactive_history = []
if "supplement_preview" not in st.session_state:
    st.session_state.supplement_preview = None   # {"question": str, "text": str}
if "graph_search" not in st.session_state:
    st.session_state.graph_search = ""
if "graph_filter" not in st.session_state:
    st.session_state.graph_filter = ["Sources", "DataPoints", "Entities"]


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR: SYSTEM AUDIT LEDGER + API SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("<h2 style='font-weight:600; color:#1D1D1F; margin-bottom:4px; font-family:Cinzel, serif;'>AuRA Core</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#86868B; font-size:12px; margin-top:0; font-family:Montserrat;'>Version 4.0 (Conversational Logs)</p>",
                unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### 📊 Live Audit Ledger")
    triples_metric = st.empty()
    conflicts_metric = st.empty()
    sources_metric = st.empty()
    status_caption = st.empty()

    # Initialize metrics layout defaults
    triples_metric.metric("Graph Triples Exported", "0")
    conflicts_metric.metric("Resolved Contradictions", "0")
    sources_metric.metric("Sources Analyzed", "0")
    status_caption.caption("⚪ System status: Idle. Waiting for ingestion pipeline initiation.")

    st.markdown("---")
    if st.button("Reset Ingestion Pipeline", use_container_width=True):
        st.session_state.cached_state = None
        st.session_state.refined_query = None
        st.session_state.chat_history = [
            ("assistant", "Hello! I am AuRA Guide, your research onboarding assistant. What topic or technical question would you like to investigate today?")
        ]
        st.session_state.interactive_history = []
        st.session_state.supplement_preview = None
        st.rerun()

    # ── ⚙️ API KEY SETTINGS PANEL ──────────────────────────────────────────
    st.markdown("---")
    with st.expander("⚙️ API Key Settings", expanded=False):
        st.caption("Configure API keys. Saving updates the local `.env` environment file.")

        new_gemini = st.text_input(
            "Gemini API Key",
            value=os.environ.get("GEMINI_API_KEY", ""),
            type="password",
            key="sidebar_gemini_key"
        )
        new_tavily = st.text_input(
            "Tavily API Key",
            value=os.environ.get("TAVILY_API_KEY", ""),
            type="password",
            key="sidebar_tavily_key"
        )
        new_s2 = st.text_input(
            "Semantic Scholar API Key (optional)",
            value=os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
            type="password",
            key="sidebar_s2_key"
        )

        if st.button("💾 Save Keys permanently", use_container_width=True):
            gemini_val = new_gemini.strip()
            tavily_val = new_tavily.strip()
            s2_val = new_s2.strip()

            # Save in-memory
            os.environ["GEMINI_API_KEY"] = gemini_val
            settings.__dict__["GEMINI_API_KEY"] = gemini_val
            os.environ["TAVILY_API_KEY"] = tavily_val
            settings.__dict__["TAVILY_API_KEY"] = tavily_val
            os.environ["SEMANTIC_SCHOLAR_API_KEY"] = s2_val

            # Write to .env
            save_keys_to_dotenv(gemini_val, tavily_val, s2_val)
            st.success("✅ Keys saved permanently to `.env`!")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WORKSPACE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<h1 style='font-weight:600; letter-spacing:-1px; font-family:Cinzel, serif; text-align:center; margin-top:10px;'>AuRA // Your Autonomous Research Assistant</h1>",
            unsafe_allow_html=True)

# Render Workspace based on state branching
if not st.session_state.cached_state:
    # --- ONBOARDING CHAT WINDOW ---
    st.markdown("<p style='text-align:center; color:#555555; font-size:14px; margin-bottom:20px;'>AuRA will validate and refine your prompt before launching the search pipeline.</p>", unsafe_allow_html=True)
    
    # Render chat history
    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)

    # Input textbox for chat
    if user_message := st.chat_input("Suggest a topic framework..."):
        # Display user message instantly
        st.session_state.chat_history.append(("user", user_message))
        st.rerun()
        
    # Execute validation loop if user sent a message
    if st.session_state.chat_history[-1][0] == "user":
        latest_user_message = st.session_state.chat_history[-1][1]
        with st.spinner("Analyzing query framework..."):
            validation = validate_and_refine_query(latest_user_message, st.session_state.chat_history[:-1])
            
        st.session_state.chat_history.append(("assistant", validation.response))
        if validation.is_valid and not validation.is_too_vague:
            st.session_state.refined_query = validation.refined_query
        else:
            st.session_state.refined_query = None
        st.rerun()

    # If query is fully refined and validated, show the launch panel
    if st.session_state.refined_query:
        st.markdown("<br/>", unsafe_allow_html=True)
        st.success(f"**Research Blueprint compiled successfully!** Ready to investigate: *\"{st.session_state.refined_query}\"*")
        
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            if st.button("Launch Multi-Agent Investigation", type="primary", use_container_width=True):
                with st.status("🧠 Executing Adversarial State Graph...", expanded=True) as status:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def run_and_stream_graph():
                        final_res = {}
                        status.write("🚀 Initializing adversarial state graph workflow...")
                        initial_state = ResearchState(user_query=st.session_state.refined_query)
                        
                        # Consume LangGraph node updates sequentially
                        async for event in aura_app.astream(initial_state):
                            for node_name, output in event.items():
                                if node_name == "scout":
                                    status.write("🔍 **Scout Agent**: Query optimized. Scraped web sources and calculated credibility ratings.")
                                elif node_name == "librarian":
                                    status.write("📚 **Librarian Agent**: Structuring in-memory cache matrices to trigger prefix-caching.")
                                elif node_name == "auditor":
                                    status.write("🔬 **Auditor Agent**: Mining semantic fact triples and syncing nodes/edges to Neo4j graph database...")
                                    conflicts = output.get("conflicts", [])
                                    target = output.get("active_routing_target", "synthesize")
                                    if target == "loopback":
                                        status.write(f"⚠️ **Divergence Gate**: Detected {len(conflicts)} semantic contradictions! Dispatched tie-breaker searches...")
                                    else:
                                        status.write("🟢 **Divergence Gate**: Verified factual consensus.")
                                elif node_name == "synthesizer":
                                    status.write("📄 **Synthesizer Agent**: Compiling inline citations and generating the final white-paper report...")
                            
                            # Accumulate state keys
                            for k, v in event.items():
                                if isinstance(v, dict):
                                    final_res.update(v)
                        return final_res
                    
                    try:
                        final_state = loop.run_until_complete(run_and_stream_graph())
                        status.update(label="✅ Research Verification Concluded!", state="complete")
                        st.session_state.cached_state = final_state
                        st.rerun()
                    except Exception as err:
                        status.update(label="❌ Graph Execution Interrupted", state="error")
                        st.error(f"E2E Graph Pipeline failed: {err}")

else:
    # --- FULL WIDTH WORKSPACE (RESEARCH DISPLAY) ---
    state_ref = st.session_state.cached_state

    # Safe extraction depending on dict vs object
    if isinstance(state_ref, dict):
        kg_data = state_ref.get("knowledge_graph", [])
        conflicts_data = state_ref.get("conflicts", [])
        report_data = state_ref.get("final_report", "No report text recovered.")
    else:
        kg_data = getattr(state_ref, "knowledge_graph", [])
        conflicts_data = getattr(state_ref, "conflicts", [])
        report_data = getattr(state_ref, "final_report", "No report text recovered.")

    # Count source types
    raw_docs = state_ref.get("raw_documents", []) if isinstance(state_ref, dict) else getattr(state_ref, "raw_documents", [])
    academic_count = sum(1 for d in raw_docs if d.get("source_type") == "academic")
    web_count = len(raw_docs) - academic_count

    # Update sidebar ledger metrics instantly
    triples_metric.metric("Graph Triples Exported", str(len(kg_data)))
    conflicts_metric.metric("Resolved Contradictions", str(len(conflicts_data)))
    sources_metric.metric("Sources Analyzed", f"{len(raw_docs)} ({academic_count} academic)")

    if len(conflicts_data) == 0:
        status_caption.caption(
            "🟢 System Data Status: Perfect Consensus Reality. No historical timeline data mismatches detected.")
    else:
        status_caption.caption(
            f"🟡 System Data Status: Active Divergence Resolved. Fixed {len(conflicts_data)} architectural mismatch vectors.")

    # --- TECHNICAL SYNTHESIS PAPER ---
    st.markdown("<h3 style='font-family:Cinzel, serif; font-weight:500; font-size:1.4em; margin-bottom:5px;'>📄 Technical Synthesis Paper</h3>", unsafe_allow_html=True)

    # Render the report inside the paper-theme wrapper block styled via CSS
    st.markdown('<div class="paper-theme">', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(report_data or "No report content built.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── DOWNLOAD & EXPORT BUTTONS ─────────────────────────────────────────
    if report_data:
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        with dl_col1:
            st.download_button(
                label="📥 Download Report (.md)",
                data=report_data,
                file_name="aura_research_report.md",
                mime="text/markdown",
                use_container_width=True
            )
        with dl_col2:
            if kg_data:
                st.download_button(
                    label="📊 Export Triples (.json)",
                    data=json.dumps(kg_data, indent=2),
                    file_name="aura_graph_triples.json",
                    mime="application/json",
                    use_container_width=True
                )
            else:
                st.button("📊 Export Triples (.json)", disabled=True, use_container_width=True)
        with dl_col3:
            if kg_data:
                st.download_button(
                    label="📋 Export Triples (.csv)",
                    data=build_triples_csv(kg_data),
                    file_name="aura_graph_triples.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.button("📋 Export Triples (.csv)", disabled=True, use_container_width=True)

    st.markdown("<hr style='border-top: 1px solid #E3DED2;'>", unsafe_allow_html=True)

    # ── SMART ACADEMIC INQUIRY DIALOG ────────────────────────────────────
    st.markdown("<h3 style='font-family:Cinzel, serif; font-weight:500; font-size:1.25em;'>💬 Academic Inquiry Dialog</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#555555; font-size:13.5px; margin-top:0;'>Ask follow-up questions. AuRA first checks the compiled report cache — if the answer isn't there, it performs a lightweight web search and offers to embed the findings into the report.</p>",
        unsafe_allow_html=True)

    local_question = st.text_input(
        "Ask a follow-up question about this report:",
        key="local_q",
        label_visibility="collapsed",
        placeholder="e.g. What other approaches have been proposed since this report?"
    )

    if st.button("Submit Question", use_container_width=True, key="inquiry_submit"):
        if local_question.strip():
            with st.spinner("Checking report cache..."):
                cache_result = inquire_with_cache(local_question.strip(), report_data)

            if cache_result.found_in_cache:
                # Answer found in cache — add to history directly
                st.session_state.interactive_history.append((local_question.strip(), cache_result.answer, "cache"))
                st.session_state.supplement_preview = None
                st.rerun()
            else:
                # Not in cache — do lightweight web search
                with st.spinner("Not found in cache. Searching the web for additional context..."):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    search_results = loop.run_until_complete(
                        _tavily_quick_search(local_question.strip(), os.environ.get("TAVILY_API_KEY", settings.TAVILY_API_KEY))
                    )
                    if search_results:
                        supplement_text = synthesize_supplement(local_question.strip(), search_results)
                        st.session_state.supplement_preview = {
                            "question": local_question.strip(),
                            "text": supplement_text
                        }
                    else:
                        st.session_state.interactive_history.append((
                            local_question.strip(),
                            "This topic was not found in the compiled report cache, and a live web search returned no usable results.",
                            "cache"
                        ))
                        st.session_state.supplement_preview = None
                st.rerun()

    # ── SUPPLEMENTARY PREVIEW BLOCK ───────────────────────────────────────
    if st.session_state.supplement_preview:
        preview = st.session_state.supplement_preview
        st.markdown(
            f"""<div class="supplement-preview">
<div class="supplement-label">🌐 Web Supplementary Research — Not in original cache</div>
<strong>Q: {preview['question']}</strong>
</div>""",
            unsafe_allow_html=True
        )
        st.markdown(preview["text"])

        embed_col, discard_col = st.columns(2)
        with embed_col:
            if st.button("✅ Embed into Report", use_container_width=True, key="embed_btn"):
                with st.spinner("Integrating supplementary findings into the report..."):
                    updated_report = embed_supplement_into_report(report_data, preview["text"])
                    # Persist updated report back to session state
                    if isinstance(st.session_state.cached_state, dict):
                        st.session_state.cached_state["final_report"] = updated_report
                    else:
                        st.session_state.cached_state.final_report = updated_report
                    st.session_state.interactive_history.append((
                        preview["question"],
                        "✅ Supplementary findings have been seamlessly embedded into the report above.",
                        "embedded"
                    ))
                    st.session_state.supplement_preview = None
                st.rerun()
        with discard_col:
            if st.button("✗ Discard", use_container_width=True, key="discard_btn"):
                st.session_state.interactive_history.append((
                    preview["question"],
                    "Supplementary results were discarded.",
                    "discarded"
                ))
                st.session_state.supplement_preview = None
                st.rerun()

    # ── INQUIRY HISTORY ───────────────────────────────────────────────────
    for q, ans, source in reversed(st.session_state.interactive_history):
        st.markdown(f"**Q: {q}**")
        badge = ""
        if source == "embedded":
            badge = "<span style='font-size:11px; background:#D1FAE5; color:#065F46; padding:2px 7px; border-radius:10px; font-family:Montserrat; font-weight:600; margin-left:8px;'>EMBEDDED</span>"
        elif source == "discarded":
            badge = "<span style='font-size:11px; background:#FEE2E2; color:#991B1B; padding:2px 7px; border-radius:10px; font-family:Montserrat; font-weight:600; margin-left:8px;'>DISCARDED</span>"
        st.markdown(
            f"<div style='background-color:#FFFFFF; border: 1px solid #E3DED2; padding:12px; border-radius:4px; font-size:14px; margin-bottom:12px; font-family: Lora, serif; line-height: 1.6; color:#333333;'>{badge}{ans}</div>",
            unsafe_allow_html=True)

    st.markdown("<hr style='border-top: 1px solid #E3DED2;'>", unsafe_allow_html=True)

    # --- DISPUTE LOG & GRAPH ---
    conflict_label = f"⚠️ Dispute & Contradiction Log ({len(conflicts_data)} conflicts found)" if conflicts_data else "✅ Dispute & Contradiction Log (No conflicts detected)"
    with st.expander(conflict_label, expanded=True):
        if not conflicts_data:
            st.success("Consensus Reality: Zero data contradictions or temporal conflicts flagged during audit cycles.")
        else:
            for conflict in conflicts_data:
                source_a_url = conflict.get('source_a_url', '')
                source_b_url = conflict.get('source_b_url', '')
                clash_a_text = conflict.get('clash_a', '')
                clash_b_text = conflict.get('clash_b', '')

                st.markdown(f"""
<div class="conflict-ledger">
<div class="conflict-title">Conflict Target: {conflict.get('subject', 'Unknown')}</div>
<div class="conflict-detail">
<strong>Source Vector A:</strong>

{clash_a_text}

<strong>Source Vector B:</strong>

{clash_b_text}
</div>
</div>
""", unsafe_allow_html=True)

    # ── INTERACTIVE EVIDENCE GRAPH ────────────────────────────────────────
    with st.expander("🕸️ Interactive Evidence Graph", expanded=True):
        if not kg_data:
            st.info("No semantic knowledge graph nodes generated.")
        else:
            # Graph controls
            ctrl_col1, ctrl_col2 = st.columns([1, 1])
            with ctrl_col1:
                graph_search_input = st.text_input(
                    "🔍 Search nodes",
                    value=st.session_state.graph_search,
                    key="graph_search_input",
                    placeholder="Type a keyword to highlight matching nodes...",
                    label_visibility="collapsed"
                )
                if graph_search_input != st.session_state.graph_search:
                    st.session_state.graph_search = graph_search_input
                    st.rerun()
            with ctrl_col2:
                graph_filter_input = st.multiselect(
                    "Filter by node type",
                    options=["Sources", "DataPoints", "Entities"],
                    default=st.session_state.graph_filter,
                    key="graph_filter_input",
                    label_visibility="collapsed"
                )
                if graph_filter_input != st.session_state.graph_filter:
                    st.session_state.graph_filter = graph_filter_input
                    st.rerun()

            visible = st.session_state.graph_filter or ["Sources", "DataPoints", "Entities"]
            st.caption(
                f"Click ⛶ Fullscreen inside the graph to expand it. Drag nodes to explore. Hover edges for confidence scores. "
                f"Showing: {', '.join(visible)}."
            )
            graph_html = render_interactive_graph(
                kg_data,
                search_term=st.session_state.graph_search,
                visible_types=visible
            )
            components.html(graph_html, height=480, scrolling=False)