"""
Recursive Deep Research Engine.

Methodology: MSDR (Multi-Source Deep Research)

Phase 1: QUERY EXPANSION - Generate sub-queries from the main question
Phase 2: PARALLEL SEARCH - Search multiple sources per sub-query
Phase 3: CONTENT EXTRACTION - Extract & summarize each source
Phase 4: RECURSIVE DEEP-DIVE - For each sub-topic, go deeper
Phase 5: SYNTHESIS - Combine findings into a coherent report

The engine implements:
- Breadth-first discovery (wide search first)
- Depth-first follow-up (drill into interesting findings)
- Source triangulation (cross-reference multiple sources)
- Gap analysis (identify what's missing and search more)
"""
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from config import (
    BRIDGE_URL, DEFAULT_MODEL_ID, MAX_DEPTH, MAX_SOURCES_PER_QUERY,
    MAX_SUB_QUERIES, REPORTS_DIR
)
from scraper import Scraper
from extractor import extract_main_content, extract_metadata


class ResearchNode:
    def __init__(self, query, depth=0, parent=None):
        self.query = query
        self.depth = depth
        self.parent = parent
        self.sources = []
        self.summary = ""
        self.children = []
        self.key_findings = []

    def to_dict(self):
        return {
            "query": self.query,
            "depth": self.depth,
            "sources": self.sources,
            "summary": self.summary,
            "key_findings": self.key_findings,
            "children": [c.to_dict() for c in self.children],
        }


class DeepResearcher:
    def __init__(self, model_id=None, use_obscura=False):
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.scraper = Scraper(prefer_obscura=use_obscura)
        self._request_count = 0
        self._last_request_time = 0

    def _ask_llm(self, prompt, max_tokens_hint=2000):
        import httpx
        self._rate_limit_wait()
        for attempt in range(3):
            try:
                r = httpx.post(
                    f"{BRIDGE_URL}/chat/completions",
                    json={
                        "message": prompt,
                        "agentId": self.model_id,
                        "stream": False,
                    },
                    timeout=120,
                )
                if r.status_code == 429:
                    print(f"  [RATE LIMITED] waiting 60s...")
                    time.sleep(60)
                    continue
                r.raise_for_status()
                data = r.json()
                if data.get("finishedReason") == "completed":
                    return data["content"]["text"]
                error = data.get("errorMessage", "Unknown")
                if "429" in str(error) or "rate" in str(error).lower():
                    print(f"  [RATE LIMITED via API] waiting 60s...")
                    time.sleep(60)
                    continue
                return f"[LLM ERROR: {error}]"
            except Exception as e:
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                return f"[BRIDGE ERROR: {e}]"
        return "[LLM ERROR: Rate limit exceeded after retries]"

    def _rate_limit_wait(self):
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 3.0
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _expand_query(self, question):
        prompt = f"""Tu es un assistant de recherche. Decompose la question suivante en {MAX_SUB_QUERIES} sous-questions precises pour une recherche approfondie.

QUESTION: {question}

Genere exactement {MAX_SUB_QUERIES} sous-questions, une par ligne, numerotees. Chaque sous-question doit explorer un angle different.
Ne reponds rien d'autre que les sous-questions."""
        response = self._ask_llm(prompt)
        queries = []
        for line in response.split("\n"):
            line = line.strip()
            if line and any(line.startswith(str(i)) for i in range(1, 100)):
                line = line.split(".", 1)[-1].strip() if "." in line else line
            if line and len(line) > 10:
                queries.append(line)
        return queries[:MAX_SUB_QUERIES]

    def _search_sources(self, query, max_sources=MAX_SOURCES_PER_QUERY):
        print(f"  [SEARCH] {query[:80]}...")
        import httpx
        try:
            r = httpx.post(
                f"{BRIDGE_URL}/chat/completions",
                json={
                    "message": f"Cherche sur le web et donne-moi les URLs de {max_sources} sources fiables pour repondre a cette question: {query}. Retourne UNIQUEMENT les URLs, une par ligne, format: - https://...  N'ajoute pas de texte supplementaire.",
                    "agentId": self.model_id,
                    "stream": False,
                    "enableWebSearch": True,
                },
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("finishedReason") == "completed":
                text = data["content"]["text"]
                urls = []
                import re
                for match in re.finditer(r"https?://[^\s\)\]]+", text):
                    urls.append({"url": match.group(0).rstrip(".,;:"), "title": ""})
                return urls[:max_sources]
            return []
        except Exception as e:
            print(f"  [SEARCH ERROR] {e}")
            return []

    def _fetch_and_extract(self, url):
        print(f"  [FETCH] {url[:80]}...")
        try:
            html = self.scraper.fetch(url, prefer_text=True)
            content = extract_main_content(html)
            meta = extract_metadata(html)
            return {
                "url": url,
                "title": meta["title"],
                "description": meta["description"],
                "content": content[:8000],
                "publish_date": meta["publish_date"],
            }
        except Exception as e:
            return {
                "url": url,
                "title": "Fetch failed",
                "content": f"[ERROR: {e}]",
                "error": str(e),
            }

    def _summarize_source(self, source, query):
        content = source.get("content", "")[:5000]
        if not content.strip() or content.startswith("[ERROR"):
            return "Source inaccessible ou erreur de fetch."

        prompt = f"""Resume le contenu suivant en 2-3 phrases, en te concentrant sur les informations pertinentes a la question: "{query}"

CONTENU:
{content}

Resume (en francais, 2-3 phrases max):"""
        return self._ask_llm(prompt, max_tokens_hint=500)

    def _extract_key_findings(self, sources_with_summaries, query):
        if not sources_with_summaries:
            return []

        summaries_text = "\n\n".join(
            f"SOURCE {i+1} ({s.get('title', 'N/A')}): {s.get('summary', '')}"
            for i, s in enumerate(sources_with_summaries[:5])
        )

        prompt = f"""A partir des sources suivantes, extrais 3-5 faits cles pertinents a la question: "{query}"

{summaries_text[:4000]}

Liste chaque fait en une phrase courte, en francais. Un fait par ligne, commence par un tiret."""
        response = self._ask_llm(prompt, max_tokens_hint=500)
        findings = []
        for line in response.split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line and len(line) > 15:
                findings.append(line)
        return findings[:5]

    def _generate_followup_queries(self, node):
        if node.depth >= MAX_DEPTH:
            return []

        findings_text = "\n".join(f"- {f}" for f in node.key_findings[:3])
        if not findings_text:
            return []

        prompt = f"""A partir de ces decouvertes sur "{node.query}", genEre 2-3 questions de suivi pour approfondir.

DECOUVERTES:
{findings_text}

Genere une question par ligne. Sois concis."""
        response = self._ask_llm(prompt, max_tokens_hint=300)
        queries = []
        for line in response.split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line and len(line) > 10:
                queries.append(line)
        return queries[:3]

    def _synthesize_report(self, root_node, original_question):
        all_findings = self._collect_all_findings(root_node)
        findings_text = "\n".join(f"- {f}" for f in all_findings[:30])

        prompt = f"""Redige un rapport de recherche complet et structure en reponse a la question suivante.

QUESTION PRINCIPALE: {original_question}

FAITS COLLECTES A TRAVERS LA RECHERCHE:
{findings_text[:6000]}

Redige un rapport bien structure avec:
1. RESUME EXECUTIF (3-4 phrases)
2. ANALYSE DETAILLEE (par themes, avec references aux sources)
3. CONCLUSIONS ET RECOMMENDATIONS

Sois exhaustif, cite les sources, utilise le markdown pour le formatage."""
        return self._ask_llm(prompt, max_tokens_hint=4000)

    def _collect_all_findings(self, node):
        findings = list(node.key_findings)
        for child in node.children:
            findings.extend(self._collect_all_findings(child))
        return findings

    def _collect_all_sources(self, node):
        sources = list(node.sources)
        for child in node.children:
            sources.extend(self._collect_all_sources(child))
        return sources

    def research(self, question):
        print(f"\n{'='*60}")
        print(f"DEEP RESEARCH: {question}")
        print(f"{'='*60}")

        root = ResearchNode(query=question, depth=0)

        print("\n[PHASE 1] Query Expansion...")
        sub_queries = self._expand_query(question)
        print(f"  Generated {len(sub_queries)} sub-queries")
        for q in sub_queries:
            print(f"    -> {q[:80]}")

        for sq in sub_queries:
            print(f"\n[PHASE 2] Searching: {sq[:60]}...")
            child = ResearchNode(query=sq, depth=1, parent=root)

            sources = self._search_sources(sq)
            print(f"  Found {len(sources)} sources")

            for source in sources:
                result = self._fetch_and_extract(source["url"])
                source.update(result)

                if not result.get("content", "").startswith("[ERROR"):
                    source["summary"] = self._summarize_source(result, sq)
                else:
                    source["summary"] = "Source indisponible."

                child.sources.append(source)
                time.sleep(0.3)

            child.key_findings = self._extract_key_findings(
                child.sources, sq
            )
            root.children.append(child)

        print(f"\n[PHASE 3] Recursive deep-dive (depth={MAX_DEPTH})...")
        for child in root.children:
            followups = self._generate_followup_queries(child)
            for fq in followups:
                grandchild = ResearchNode(query=fq, depth=2, parent=child)
                sources = self._search_sources(fq, max_sources=3)
                for source in sources:
                    result = self._fetch_and_extract(source["url"])
                    source.update(result)
                    if not result.get("content", "").startswith("[ERROR"):
                        source["summary"] = self._summarize_source(result, fq)
                    else:
                        source["summary"] = "Source indisponible."
                    grandchild.sources.append(source)
                    time.sleep(0.3)
                grandchild.key_findings = self._extract_key_findings(
                    grandchild.sources, fq
                )
                child.children.append(grandchild)

        print("\n[PHASE 4] Report Synthesis...")
        report = self._synthesize_report(root, question)

        total_sources = len(self._collect_all_sources(root))
        total_findings = len(self._collect_all_findings(root))

        result = {
            "question": question,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "model_used": str(self.model_id),
            "methodology": "MSDR (Multi-Source Deep Research)",
            "stats": {
                "depth": MAX_DEPTH,
                "sub_queries": len(sub_queries),
                "total_sources": total_sources,
                "total_findings": total_findings,
            },
            "research_tree": root.to_dict(),
            "report": report,
        }

        report_path = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n{'='*60}")
        print(f"DONE. {total_findings} findings from {total_sources} sources.")
        print(f"Report saved: {report_path}")
        print(f"{'='*60}")

        return result


async def deep_research(question, model_id=None, use_obscura=False):
    researcher = DeepResearcher(model_id=model_id, use_obscura=use_obscura)
    return researcher.research(question)
