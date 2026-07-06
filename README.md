<p align="center">
  <img src="https://img.shields.io/badge/version-v0.1_beta-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/scraper-Obscura%20%2B%20httpx-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/methodology-MSDR-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/anti--detect-Oui-red?style=for-the-badge" />
</p>

<p align="center">
  <h1 align="center">Deep Researcher v0.1</h1>
  <p align="center"><i>Moteur de recherche profonde multi-source avec anti-detection integree.<br>Le premier a combiner scraping furtif + recherche recursive + synthese multi-sources en open-source.</i></p>
</p>

---

## Le probleme

Tous les outils de deep research existants ont le meme defaut : **ils se font bloquer**. 

GPT Researcher (28k stars), STORM (30k stars), Deep Research (19k stars) — ils dependent tous d'APIs tierces (Tavily, Firecrawl, Serper) pour le scraping. Ces APIs coutent cher et ne garantissent pas l'acces aux sites proteges.

Les outils qui font du scraping direct (Crawl4AI, Jina Reader) n'ont pas de couche de recherche/synthese. Ce sont juste des extracteurs.

**Notre solution : Obscura** — un navigateur headless de 30 MB ecrit en Rust, avec anti-detection integree. Zero blocage. Zero cout.

---

## Paysage concurrentiel (Juillet 2026)

| Projet | Stars | Type | Anti-detect | Gratuit | Deep Research |
|--------|-------|------|-------------|---------|---------------|
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | 28k | Agent de recherche | ❌ | Partiel | ✅ Recursif |
| [STORM](https://github.com/stanford-oval/storm) | 30k | Curation academique | ❌ | ✅ | ✅ Multi-perspectives |
| [Firecrawl](https://github.com/mendableai/firecrawl) | 146k | API scraping | ☁️ Cloud payant | Partiel | ❌ |
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | 71k | Crawler LLM | ✅ 3 niveaux | ✅ | ❌ |
| [Browser-Use](https://github.com/browser-use/browser-use) | 103k | Automatisation nav. | ☁️ Cloud payant | Partiel | ❌ |
| [Scira](https://github.com/zaidmukaddam/scira) | 12k | Moteur recherche IA | ❌ | Partiel | ⚠️ Mode Extreme |
| [Vane](https://github.com/ItzCrazyKns/Vane) | 36k | Moteur prive | ❌ | ✅ | ❌ Superficiel |
| [Deep Research](https://github.com/dzhng/deep-research) | 19k | Agent minimal | ❌ | Partiel | ✅ Iteratif |
| [Local Deep Researcher](https://github.com/langchain-ai/local-deep-researcher) | 9k | 100% local | ❌ | ✅ | ⚠️ Boucle simple |
| [Jina Reader](https://github.com/jina-ai/reader) | 12k | URL→Markdown | ☁️ Cloud | Partiel | ❌ |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 55k | Framework multi-agents | ❌ | ✅ | ⚠️ A construire |
| [SearXNG](https://github.com/searxng/searxng) | 34k | Metamoteur | ❌ | ✅ | ❌ |
| **[Deep Researcher (nous)](https://github.com/Yormede/deep-researcher)** | **v0.1** | **Deep research + anti-detect** | **✅ Obscura** | **✅** | **✅ MSDR recursif** |

### Le gap qu'on comble

Aucun projet open-source ne combine :
1. **Scraping furtif** (anti-detect, rotation proxies, fingerprinting)
2. **Recherche recursive profonde** (3+ niveaux, multi-perspectives)
3. **Synthese multi-sources** (rapport structure, citations)
4. **100% gratuit** (zero API payante necessaire)

C'est ce qu'on construit.

---

## Methodologie MSDR (Multi-Source Deep Research)

```
1. QUERY EXPANSION
   └─ Le LLM decompose la question en sous-questions (max 7)

2. RECHERCHE INTELLIGENTE
   └─ Claude cherche sur le web et selectionne les URLs pertinentes

3. EXTRACTION FURTIVE
   └─ Obscura (ou httpx fallback) scrape chaque page
   └─ Algorithme Readability-like extrait le contenu pertinent

4. DEEP-DIVE RECURSIF (3 niveaux de profondeur)
   └─ Pour chaque decouverte prometteuse → nouvelle question → nouvelle recherche

5. SYNTHESE FINALE
   └─ Rapport structure : resume, analyse thematique, conclusions, sources
```

---

## Installation rapide

```bash
git clone https://github.com/Yormede/deep-researcher.git
cd deep-researcher
pip install -r requirements.txt

# Optionnel : Obscura pour l'anti-detection
curl -LO https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-linux.tar.gz
tar xzf obscura-x86_64-linux.tar.gz
export OBSCURA_BIN="./obscura"
```

## Utilisation

```bash
# CLI
python server.py "Comment fonctionne le Bitcoin ?"

# Avec anti-detection
python server.py "Dernieres tendances IA 2026" --obscura --model 50

# Mode API
python server.py --serve --port 8766
curl -X POST http://localhost:8766/research \
  -H "Content-Type: application/json" \
  -d '{"question": "Explique la fission nucleaire", "model_id": 50}'
```

Les rapports sont sauvegardes dans `storage/reports/`.

---

## Architecture

```
deep-researcher/
├── researcher.py        # Moteur MSDR
├── scraper.py           # Dual scraper (Obscura + httpx)
├── extractor.py         # Content extractor (Readability-like)
├── server.py            # CLI + API server
├── config/__init__.py   # Configuration
├── storage/reports/     # Rapports JSON
└── storage/cache/       # Cache HTTP
```

**Requiert :** [france-student-bridge](https://github.com/Yormede/france-student-bridge) pour les LLMs (ou n'importe quel endpoint OpenAI-compatible).

---

## Roadmap v0.2+

- [ ] Mode "quick answer" (<10s, 1 source) en plus du mode "deep research"
- [ ] Export PDF des rapports
- [ ] Interface web
- [ ] Support multi-LLM direct (sans bridge)
- [ ] Rotation de proxies automatique
- [ ] Extraction de donnees structurees (JSON schemas)
- [ ] Sources federees (fichiers locaux + APIs + BDD + web)

---

## Avertissement

> **v0.1 beta** — Ce projet est en developpement actif. Il peut cesser de fonctionner si France Student modifie son API. N'utilise pas ce projet pour du scraping abusif.

---

## Licence

MIT. Si ca t'est utile, laisse une etoile.

<p align="center">
  <a href="https://github.com/Yormede/deep-researcher">
    <img src="https://img.shields.io/github/stars/Yormede/deep-researcher?style=social" />
  </a>
</p>
