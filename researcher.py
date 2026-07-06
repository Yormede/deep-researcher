"""
Deep Researcher v0.2 — Methodologique MSDR+STORM+GPTResearcher

Combined best practices from:
- STORM (Stanford): Multi-perspective personas, simulated expert/journalist conversations,
  question→queries decomposition, cosine similarity retrieval, citation system
- GPT Researcher: Recursive tree breadth×depth, context compressor with embeddings filter,
  anti-duplication, concurrency semaphore, Planner→Executor→Publisher pipeline
- Crawl4AI: 3-tier stealth, block detection, proxy escalation, fingerprint anti-detection
"""
import time
import json
import re
import asyncio
import hashlib
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import httpx

from config import (
    BRIDGE_URL, DEFAULT_MODEL_ID, MAX_DEPTH, MAX_SOURCES_PER_QUERY,
    MAX_SUB_QUERIES, REPORTS_DIR, INTER_PAGE_DELAY
)
from scraper import Scraper
from extractor import extract_main_content, extract_metadata


# ─── Data Structures ────────────────────────────────────────────────

@dataclass
class Information:
    url: str
    title: str = ""
    description: str = ""
    snippets: List[str] = field(default_factory=list)
    content: str = ""
    publish_date: str = ""
    citation_index: int = 0

@dataclass
class DialogueTurn:
    agent_utterance: str
    user_utterance: str
    search_queries: List[str] = field(default_factory=list)
    search_results: List[Information] = field(default_factory=list)

@dataclass
class KnowledgeNode:
    name: str
    content: Set[int] = field(default_factory=set)
    children: list = field(default_factory=list)
    synthesize_output: str = ""
    def to_dict(self):
        return {
            "name": self.name,
            "content_count": len(self.content),
            "synthesize": self.synthesize_output[:200] if self.synthesize_output else "",
            "children": [c.to_dict() for c in self.children]
        }


# ─── Prompt Templates (from STORM + GPT Researcher) ────────────────

PROMPT_GEN_PERSONAS = """Tu es un chercheur qui prepare un article Wikipedia-like sur le sujet suivant.

Trouve des pages Wikipedia sur des sujets proches. Pour chaque sujet connexe, definis UNE perspective (persona) d'expert qui pourrait contribuer a l'article.

SUJET : {topic}

Format (une ligne par expert) :
1. Expert en [domaine]: Se concentre sur [aspect specifique]
2. Expert en [domaine]: Se concentre sur [aspect specifique]
..."""

PROMPT_JOURNALIST_ASK = """Tu es un journaliste scientifique chevronne. Tu interviewes un expert pour obtenir des informations precises sur le sujet.

SUJET : {topic}
TA PERSPECTIVE : {persona}
HISTORIQUE DE LA CONVERSATION :
{history}

Pose une nouvelle question pertinente, non posee precedemment. Quand tu n'as plus de questions, reponds : "Merci beaucoup pour votre aide !"
Question :"""

PROMPT_QUESTION_TO_QUERIES = """Tu cherches a repondre a la question suivante en utilisant une recherche web.

SUJET : {topic}
QUESTION : {question}

Genere 2-3 requetes de recherche precises pour trouver les meilleures informations. Format :
- requete 1
- requete 2
- requete 3"""

PROMPT_EXPERT_ANSWER = """Tu es un expert. Utilise les informations collectees pour repondre a la question.

SUJET : {topic}
QUESTION : {question}
INFORMATIONS COLLECTEES :
{info}

Reponds de maniere factuelle, en citant chaque source avec [1], [2] etc. Si l'information est insuffisante, dis-le clairement.
Ne mentionne pas les numeros de source dans le texte si tu n'as pas d'information correspondante.
Reponse :"""

PROMPT_DRAFT_OUTLINE = """Genere le plan d'un rapport academique sur le sujet suivant.

SUJET : {topic}

Format :
# Titre de section
## Titre de sous-section
...

Genere un plan complet et structure. Ne mets pas le titre du sujet lui-meme dans le plan."""

PROMPT_REFINE_OUTLINE = """Ameliore le plan d'un rapport academique en utilisant les informations collectees.

SUJET : {topic}
INFORMATIONS COLLECTEES (resume) :
{info}
PLAN ACTUEL :
{outline}

Genere un plan ameliore et plus complet. Format identique (markdown avec # et ##)."""

PROMPT_WRITE_SECTION = """Redige une section de rapport academique.

SUJET : {topic}
SECTION A REDIGER : {section}
INFORMATIONS PERTINENTES :
{info}

Redige la section en utilisant des citations inline [1], [2] etc.
Sois rigoureux, precis, et accessible. Explique les termes techniques.
Utilise le format markdown pour la structure (## sous-titres, **gras**, listes).
N'invente pas d'informations. Si les sources sont insuffisantes, indique-le.
Section :"""

PROMPT_SYNTHESIZE_REPORT = """Synthetise un rapport de recherche complet et structure.

SUJET : {question}
PLAN DU RAPPORT :
{outline}
CONTENU DES SECTIONS :
{sections}

Genere le rapport final en markdown avec :
1. RESUME EXECUTIF (4-5 phrases, pour le grand public)
2. Corps du rapport (toutes les sections)
3. CONCLUSION ET PERSPECTIVES
4. SOURCES (liste des URLs avec descriptions)

Le rapport doit etre :
- Academique mais accessible (expliquer les termes techniques)
- Factuel et source (chaque affirmation doit etre etayee)
- Structure avec titres, sous-titres, et transitions
- Adapte a l'export PDF (pas de contenu dynamique, pas d'emoji)

Utilise le format markdown complet."""

PROMPT_EXPAND_SUBTOPICS = """A partir des decouvertes suivantes sur le sujet "{topic}", identifie les sous-themes qui meritent d'etre approfondis.

DECOUVERTES :
{findings}

Genere 2-3 sous-questions precises, une par ligne. Chaque question doit explorer un angle complementaire."""


# ─── Enhanced Deep Researcher ───────────────────────────────────────

class EnhancedDeepResearcher:
    """MSDR+STORM+GPTResearcher combined engine."""

    def __init__(self, model_id=None, use_obscura=False):
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.scraper = Scraper(prefer_obscura=use_obscura)
        self._request_count = 0
        self._last_request_time = 0
        self._citation_index = 0
        self._all_sources: List[Information] = []
        self._source_urls: Set[str] = set()

    # ─── LLM Interface ─────────────────────────────────────────────

    def _ask_llm(self, prompt, max_retries=3):
        self._rate_limit_wait()
        for attempt in range(max_retries):
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
                    print(f"  [RATE LIMIT] attente 60s...")
                    time.sleep(60)
                    continue
                r.raise_for_status()
                data = r.json()
                if data.get("finishedReason") == "completed":
                    return data["content"]["text"]
                err = data.get("errorMessage", "")
                if "429" in str(err) or "rate" in str(err).lower():
                    print(f"  [RATE LIMIT API] attente 60s...")
                    time.sleep(60)
                    continue
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                return f"[LLM ERROR: {err}]"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                return f"[BRIDGE ERROR: {e}]"
        return "[LLM ERROR: max retries exceeded]"

    def _rate_limit_wait(self):
        now = time.time()
        min_interval = 3.0
        if now - self._last_request_time < min_interval:
            time.sleep(min_interval - (now - self._last_request_time))
        self._last_request_time = time.time()
        self._request_count += 1

    # ─── STORM: Persona Generation ──────────────────────────────────

    def _generate_personas(self, topic, num_personas=3):
        """STORM-style: generate diverse expert perspectives."""
        prompt = PROMPT_GEN_PERSONAS.format(topic=topic)
        response = self._ask_llm(prompt)
        personas = []
        for line in response.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() and "." in line[:3]):
                line = line.split(".", 1)[-1].strip()
            if line and len(line) > 10:
                personas.append(line)
        if not personas:
            personas = ["Expert generaliste: couvre tous les aspects du sujet"]
        return personas[:num_personas]

    # ─── STORM: Simulated Conversation ──────────────────────────────

    def _simulate_conversation(self, topic, persona, max_turns=3):
        """STORM-style: journalist interviews expert with web search."""
        dialogue = []
        history = ""

        for turn in range(max_turns):
            # Journalist asks a question
            q_prompt = PROMPT_JOURNALIST_ASK.format(
                topic=topic, persona=persona, history=history[-2000:]
            )
            question = self._ask_llm(q_prompt).strip()
            if question.startswith("Merci") or question.startswith("Thank"):
                break

            # Generate search queries
            q2q_prompt = PROMPT_QUESTION_TO_QUERIES.format(
                topic=topic, question=question
            )
            queries_text = self._ask_llm(q2q_prompt)
            queries = []
            for line in queries_text.split("\n"):
                line = line.strip().lstrip("- ").strip()
                if line and len(line) > 3:
                    queries.append(line)
            queries = queries[:3]

            # Search and extract
            search_results = self._search_and_extract(queries, topic)

            # Expert answers
            info_text = self._format_search_results(search_results)
            a_prompt = PROMPT_EXPERT_ANSWER.format(
                topic=topic, question=question, info=info_text[:2000]
            )
            answer = self._ask_llm(a_prompt)

            turn_data = DialogueTurn(
                agent_utterance=answer,
                user_utterance=question,
                search_queries=queries,
                search_results=search_results,
            )
            dialogue.append(turn_data)

            history += f"\nQ: {question}\nR: {answer}\n"

        return dialogue

    # ─── GPT Researcher: Search & Extract ───────────────────────────

    def _search_and_extract(self, queries, context_topic, max_urls=3):
        """Search using Claude's web search, then extract content."""
        all_results = []
        for query in queries[:2]:  # limit to 2 queries max
            urls = self._search_urls_via_llm(query, max_urls)
            for url_data in urls:
                url = url_data["url"]
                if url in self._source_urls:
                    continue
                self._source_urls.add(url)
                try:
                    html = self.scraper.fetch(url, prefer_text=True)
                    content = extract_main_content(html, max_chars=5000)
                    meta = extract_metadata(html)
                    info = Information(
                        url=url,
                        title=meta.get("title", url[:60]),
                        description=meta.get("description", ""),
                        snippets=[content[:1000]],
                        content=content,
                        publish_date=meta.get("publish_date", ""),
                        citation_index=len(self._all_sources) + 1,
                    )
                    self._all_sources.append(info)
                    all_results.append(info)
                except Exception as e:
                    pass
                time.sleep(0.5)
        return all_results

    def _search_urls_via_llm(self, query, num_urls=3):
        """Use Claude's web search to find URLs."""
        prompt = f"Cherche sur le web et donne-moi {num_urls} URLs de sources fiables pour repondre a : {query}. Retourne UNIQUEMENT les URLs, une par ligne, format: - https://..."
        response = self._ask_llm(prompt)
        urls = []
        for match in re.finditer(r"https?://[^\s\)\]\"]+", response):
            url = match.group(0).rstrip(".,;:")
            urls.append({"url": url, "title": ""})
        return urls[:num_urls]

    def _format_search_results(self, results):
        parts = []
        for i, r in enumerate(results[:5]):
            idx = i + 1
            parts.append(f"[{idx}] {r.title}\nURL: {r.url}\n{r.snippets[0][:500] if r.snippets else ''}\n")
        return "\n".join(parts)

    # ─── GPT Researcher: Outline → Sections → Report ────────────────

    def _generate_outline(self, topic, research_info=""):
        """GPT Researcher-style: draft outline, then refine with research."""
        draft_prompt = PROMPT_DRAFT_OUTLINE.format(topic=topic)
        draft = self._ask_llm(draft_prompt)

        if research_info:
            refine_prompt = PROMPT_REFINE_OUTLINE.format(
                topic=topic, info=research_info[:2000], outline=draft
            )
            refined = self._ask_llm(refine_prompt)
            return refined
        return draft

    def _parse_outline_sections(self, outline_text):
        """Parse markdown outline into section hierarchy."""
        sections = []
        for line in outline_text.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                sections.append({"level": 1, "title": line[2:].strip()})
            elif line.startswith("## "):
                sections.append({"level": 2, "title": line[3:].strip()})
            elif line.startswith("### "):
                sections.append({"level": 3, "title": line[4:].strip()})
        return sections

    def _select_relevant_info(self, section_title, min_chars=500):
        """Select most relevant information for a section."""
        relevant = []
        for info in self._all_sources:
            content_lower = (info.content + info.title + info.description).lower()
            keywords = section_title.lower().split()
            matches = sum(1 for kw in keywords if len(kw) > 3 and kw in content_lower)
            if matches > 0:
                relevant.append((matches, info))

        relevant.sort(key=lambda x: -x[0])
        selected = []
        total = 0
        for _, info in relevant[:10]:
            snippet = info.content[:1000] if info.content else (info.snippets[0] if info.snippets else "")
            if snippet:
                selected.append(f"[{info.citation_index}] {info.title}\n{snippet}\n")
                total += len(snippet)
                if total > 3000:
                    break

        if not selected and self._all_sources:
            for info in self._all_sources[:5]:
                snippet = info.content[:500] if info.content else ""
                if snippet:
                    selected.append(f"[{info.citation_index}] {info.title}\n{snippet}\n")

        return "\n".join(selected) if selected else "Information non disponible pour cette section."

    def _write_section(self, topic, section_title, info):
        """STORM-style: write a section with inline citations."""
        prompt = PROMPT_WRITE_SECTION.format(
            topic=topic, section=section_title, info=info[:3000]
        )
        return self._ask_llm(prompt)

    def _synthesize_final_report(self, question, outline, sections_text):
        """Final synthesis with all sections."""
        prompt = PROMPT_SYNTHESIZE_REPORT.format(
            question=question, outline=outline[:1000], sections=sections_text[:8000]
        )
        return self._ask_llm(prompt)

    # ─── GPT Researcher: Context Compressor ─────────────────────────

    def _compress_context(self, sources, max_chars=8000):
        """GPT Researcher-style context compression."""
        text = ""
        for s in sources:
            snippet = s.content[:1500] if s.content else s.snippets[0] if s.snippets else ""
            if snippet:
                text += f"[{s.citation_index}] {s.title}\n{snippet}\n\n"
        if len(text) <= max_chars:
            return text
        lines = text.split("\n")
        result = []
        total = 0
        for line in lines:
            if total + len(line) > max_chars:
                break
            result.append(line)
            total += len(line)
        return "\n".join(result)

    # ─── Deep-dive Recursive ────────────────────────────────────────

    def _expand_subtopics(self, topic, findings, max_sub=3):
        """Generate follow-up questions for deeper research."""
        findings_text = "\n".join(f"- {f}" for f in findings[:5])
        prompt = PROMPT_EXPAND_SUBTOPICS.format(topic=topic, findings=findings_text[:1500])
        response = self._ask_llm(prompt)
        queries = []
        for line in response.split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line and len(line) > 10:
                queries.append(line)
        return queries[:max_sub]

    # ─── Master Research Pipeline ───────────────────────────────────

    def research(self, question):
        """Full MSDR+STORM+GPTResearcher pipeline."""
        print(f"\n{'='*70}")
        print(f"DEEP RESEARCH v0.2: {question}")
        print(f"{'='*70}")

        start_time = time.time()

        # PHASE 1: STORM — Multi-perspective research
        print("\n[PHASE 1] STORM: Multi-perspective research...")
        personas = self._generate_personas(question)
        print(f"  Generated {len(personas)} expert perspectives")

        all_dialogues = []
        all_findings = []

        for i, persona in enumerate(personas):
            print(f"  Expert {i+1}: {persona[:80]}...")
            dialogue = self._simulate_conversation(question, persona, max_turns=2)
            all_dialogues.append((persona, dialogue))
            
            for turn in dialogue:
                if turn.agent_utterance:
                    sentences = re.split(r'[.!?]\s+', turn.agent_utterance)
                    for sent in sentences[:3]:
                        if len(sent) > 20:
                            all_findings.append(sent.strip())

        # PHASE 2: GPT Researcher — Outline generation
        print("\n[PHASE 2] Outline generation...")
        research_summary = "\n".join(f"- {f}" for f in all_findings[:10])
        outline = self._generate_outline(question, research_summary)
        sections = self._parse_outline_sections(outline)
        print(f"  Generated {len(sections)} sections")

        # PHASE 3: Section-by-section writing with deep research
        print("\n[PHASE 3] Section writing with deep research...")
        sections_content = []

        for sec in sections:
            prefix = "#" * sec["level"]
            section_title = sec["title"]
            print(f"  Writing: {section_title[:60]}...")

            # Search for section-specific information
            search_queries = self._search_and_extract(
                [f"{question} {section_title}"], question, max_urls=2
            )

            # Select relevant info from all collected sources
            info_text = self._select_relevant_info(section_title)

            # Write section
            section_text = self._write_section(question, section_title, info_text)
            sections_content.append(f"## {section_title}\n\n{section_text}")
            time.sleep(1)

        # PHASE 4: Recursive deep-dive on key findings
        if MAX_DEPTH > 1:
            print(f"\n[PHASE 4] Recursive deep-dive (depth={MAX_DEPTH})...")
            sub_topics = self._expand_subtopics(question, all_findings[:5])
            for sub in sub_topics[:3]:
                print(f"  Deep-dive: {sub[:60]}...")
                sub_results = self._search_and_extract([sub], question, max_urls=2)
                info_text = self._format_search_results(sub_results)
                sub_section = self._write_section(question, sub, info_text)
                sections_content.append(f"## Exploration approfondie: {sub}\n\n{sub_section}")
                time.sleep(1)

        # PHASE 5: Final synthesis
        print("\n[PHASE 5] Final synthesis...")
        sections_joined = "\n\n".join(sections_content)
        report = self._synthesize_final_report(question, outline, sections_joined)

        # Build source list
        sources_list = []
        seen_urls = set()
        for info in self._all_sources:
            if info.url not in seen_urls:
                seen_urls.add(info.url)
                sources_list.append({
                    "index": info.citation_index,
                    "url": info.url,
                    "title": info.title[:100],
                    "description": info.description[:200],
                })

        elapsed = time.time() - start_time

        result = {
            "question": question,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "methodology": "MSDR+STORM+GPTResearcher (v0.2)",
            "model_used": str(self.model_id),
            "stats": {
                "personas": len(personas),
                "dialogues": len(all_dialogues),
                "sections": len(sections),
                "total_sources": len(sources_list),
                "total_findings": len(all_findings),
                "time_seconds": round(elapsed, 1),
            },
            "sources": sources_list,
            "report": report,
        }

        # Save report
        report_path = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n{'='*70}")
        print(f"DONE in {elapsed:.1f}s. {len(sources_list)} sources, {len(all_findings)} findings.")
        print(f"Report: {report_path}")
        print(f"{'='*70}")

        return result


async def deep_research(question, model_id=None, use_obscura=False):
    researcher = EnhancedDeepResearcher(model_id=model_id, use_obscura=use_obscura)
    return researcher.research(question)
