"""
AGENT: ScholarAgent (Academic Source Layer)

Fetches real academic papers from arXiv and Semantic Scholar APIs.
Both APIs are free and require no authentication keys.

Instead of downloading and parsing PDFs (fragile, token-expensive),
we pull structured metadata + abstracts, which gives us:
  - Proper academic citations (Author, Year, Title, Venue, DOI)
  - Enough textual content (abstracts) for the Auditor to mine facts
  - Real credibility signals (citation count, venue, peer review status)
"""

import os
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from urllib.parse import quote_plus


async def search_arxiv(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Queries the arXiv API (free, no auth).
    Returns structured paper metadata including title, authors, abstract, and PDF link.
    """
    encoded_query = quote_plus(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"

    papers = []
    headers = {"User-Agent": "AuRA-ResearchAssistant/1.0 (academic research tool; contact: research@aura.ai)"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    print(f"  [Scholar/arXiv] HTTP {resp.status} — skipping arXiv results.")
                    return []
                xml_text = await resp.text()

        # Parse the Atom XML feed
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)

            # Extract authors
            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            # Extract the abstract page link and PDF link
            abs_link = ""
            pdf_link = ""
            for link_el in entry.findall("atom:link", ns):
                href = link_el.get("href", "")
                link_type = link_el.get("type", "")
                link_title = link_el.get("title", "")
                if link_title == "pdf" or "pdf" in href:
                    pdf_link = href
                elif link_type == "text/html" or ("/abs/" in href):
                    abs_link = href

            if not abs_link:
                id_el = entry.find("atom:id", ns)
                if id_el is not None and id_el.text:
                    abs_link = id_el.text.strip()

            title_text = title.text.strip().replace("\n", " ") if title is not None and title.text else "Untitled"
            abstract_text = summary.text.strip().replace("\n", " ") if summary is not None and summary.text else ""
            pub_date = published.text.strip()[:10] if published is not None and published.text else ""
            year = pub_date[:4] if pub_date else ""

            # Build a clean academic citation string
            author_str = authors[0].split()[-1] + " et al." if len(authors) > 1 else (authors[0] if authors else "Unknown")
            citation_label = f"{author_str} ({year})" if year else author_str

            papers.append({
                "title": title_text,
                "url": abs_link or pdf_link,
                "content": abstract_text,
                "authors": authors,
                "year": year,
                "venue": "arXiv",
                "doi": "",
                "citation_count": None,
                "pdf_url": pdf_link,
                "source_type": "academic",
                "academic_citation": f'{citation_label}. "{title_text}". arXiv. {pub_date}.',
            })

    except asyncio.TimeoutError:
        print("  [Scholar/arXiv] Request timed out.")
    except Exception as e:
        print(f"  [Scholar/arXiv] Error: {e}")

    return papers


async def search_semantic_scholar(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Queries the Semantic Scholar API (free tier, 100 req/5min, no key needed).
    Returns papers with citation counts, DOIs, and venue info.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,abstract,year,venue,citationCount,externalIds,url"
    }

    papers = []
    headers = {
        "User-Agent": "AuRA-ResearchAssistant/1.0 (academic research tool; contact: research@aura.ai)",
        "Accept": "application/json"
    }
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 429:
                    print(f"  [Scholar/S2] Rate limited (429) — skipping Semantic Scholar results.")
                    return []
                if resp.status != 200:
                    print(f"  [Scholar/S2] HTTP {resp.status} — skipping Semantic Scholar results.")
                    return []
                data = await resp.json()

        for paper in data.get("data", []):
            title = paper.get("title", "Untitled")
            abstract = paper.get("abstract") or ""
            year = str(paper.get("year", ""))
            venue = paper.get("venue") or "Preprint"
            citation_count = paper.get("citationCount", 0)
            s2_url = paper.get("url") or ""

            # Extract DOI if available
            ext_ids = paper.get("externalIds") or {}
            doi = ext_ids.get("DOI") or ""
            arxiv_id = ext_ids.get("ArXiv") or ""

            doi_url = f"https://doi.org/{doi}" if doi else s2_url
            if not doi_url and arxiv_id:
                doi_url = f"https://arxiv.org/abs/{arxiv_id}"

            # Build author list
            authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]

            author_str = authors[0].split()[-1] + " et al." if len(authors) > 1 else (authors[0] if authors else "Unknown")
            citation_label = f"{author_str} ({year})" if year else author_str

            # Skip papers with no abstract (they won't contribute useful content)
            if not abstract:
                continue

            papers.append({
                "title": title,
                "url": doi_url or s2_url,
                "content": abstract,
                "authors": authors,
                "year": year,
                "venue": venue,
                "doi": doi,
                "citation_count": citation_count,
                "pdf_url": "",
                "source_type": "academic",
                "academic_citation": f'{citation_label}. "{title}". *{venue}*. {year}.' + (f" DOI: {doi}" if doi else ""),
            })

    except asyncio.TimeoutError:
        print("  [Scholar/S2] Request timed out.")
    except Exception as e:
        print(f"  [Scholar/S2] Error: {e}")

    return papers


async def fetch_academic_papers(query: str, max_per_source: int = 3) -> List[Dict[str, Any]]:
    """
    Main entry point. Runs arXiv and Semantic Scholar searches concurrently,
    deduplicates by title similarity, and returns merged results.
    """
    print(f"🎓 [Scholar] Searching academic databases for: '{query}'")

    arxiv_task = search_arxiv(query, max_results=max_per_source)
    s2_task = search_semantic_scholar(query, max_results=max_per_source)

    arxiv_papers, s2_papers = await asyncio.gather(arxiv_task, s2_task)

    print(f"  [Scholar] arXiv returned {len(arxiv_papers)} papers, Semantic Scholar returned {len(s2_papers)} papers.")

    # Deduplicate across sources using normalized title matching
    seen_titles = set()
    merged = []

    # Prefer Semantic Scholar results (they have citation counts and DOIs)
    for paper in s2_papers + arxiv_papers:
        normalized = paper["title"].lower().strip()[:80]
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            merged.append(paper)

    print(f"🎓 [Scholar] Total unique academic papers fetched: {len(merged)}")
    return merged
