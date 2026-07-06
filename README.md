<p align="center">
  <img src="https://img.shields.io/badge/status-beta-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/scraper-Obscura%20%2B%20httpx-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/depth-recursive-purple?style=for-the-badge" />
</p>

<p align="center">
  <h1 align="center">Deep Researcher</h1>
  <p align="center"><i>Multi-Source Deep Research Engine — powered by Claude, anti-detect via Obscura</i></p>
</p>

---

## Pourquoi un nouveau deep researcher ?

Les outils existants (GPT Researcher, STORM, Perplexity Deep Research) ont tous le meme probleme : **ils se font bloquer** par les sites web qui detectent les scrapers.

Notre solution : **Obscura** — un navigateur headless de 30 MB ecrit en Rust, avec anti-detection integree, qui se fait passer pour un vrai Chrome. Zero blocage.

Et en fallback, un scraper HTTP classique via `httpx` quand Obscura n'est pas disponible.

---

## Methodologie MSDR (Multi-Source Deep Research)

C'est une methodologie **scientifique, reproductible et recursive** :

```
1. QUERY EXPANSION
   └─ Decompose la question en 2-7 sous-questions (via LLM)

2. RECHERCHE PARALLELE
   └─ Pour chaque sous-question, le LLM cherche sur le web et retourne les URLs

3. EXTRACTION DE CONTENU
   └─ Scrape chaque URL (Obscura ou httpx)
   └─ Extrait le contenu pertinent (algo Readability-like)
   └─ Le LLM resume chaque source en 2-3 phrases

4. DEEP-DIVE RECURSIF (3 niveaux)
   └─ Pour chaque sous-sujet prometteur, genere des questions de suivi
   └─ Re-cherche et re-extrait (max 3 niveaux de profondeur)

5. SYNTHESE FINALE
   └─ Le LLM compile toutes les decouvertes en un rapport structure :
      • Resume executif
      • Analyse detaillee par themes
      • Conclusions et recommandations
```

**Pourquoi c'est superieur :**
- **Pas de scraping naif** — le LLM choisit intelligemment les URLs a scraper
- **Traque les sources** — chaque fait est reference
- **Anti-blocage** — Obscura contourne les anti-bots
- **Reproductible** — tout est logge, chaque etape est tracable

---

## Installation

```bash
git clone https://github.com/Yormede/deep-researcher.git
cd deep-researcher
pip install -r requirements.txt
```

### Optionnel : Obscura (pour l'anti-detection)

```bash
curl -LO https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-linux.tar.gz
tar xzf obscura-x86_64-linux.tar.gz
export OBSCURA_BIN="./obscura"
```

---

## Utilisation

### Mode CLI

```bash
# Recherche simple
python server.py "Comment fonctionne le Bitcoin ?"

# Avec un modele specifique
python server.py "Qui a invente le Web ?" --model 50

# Avec Obscura (anti-detect)
python server.py "Dernieres tendances IA 2026" --obscura
```

### Mode API

```bash
# Demarrer le serveur
python server.py --serve --port 8766

# Faire une recherche
curl -X POST http://localhost:8766/research \
  -H "Content-Type: application/json" \
  -d '{"question": "Explique la fission nucleaire", "model_id": 50}'

# Lister les rapports
curl http://localhost:8766/reports

# Voir un rapport
curl http://localhost:8766/reports/report_20260706_143000.json
```

### Exemple de resultat

```json
{
  "question": "Qui a invente le World Wide Web ?",
  "stats": {
    "depth": 3,
    "sub_queries": 5,
    "total_sources": 15,
    "total_findings": 23
  },
  "report": "# Rapport de recherche\n\n## Resume executif\nLe World Wide Web a ete invente par Tim Berners-Lee en 1989..."
}
```
Les rapports sont sauvegardes dans `storage/reports/`.

---

## Configuration

| Variable | Defaut | Description |
|----------|--------|-------------|
| `BRIDGE_URL` | `http://localhost:8765` | URL du bridge France Student |
| `DEFAULT_MODEL_ID` | `50` | Modele par defaut (50=Claude Sonnet) |
| `MAX_DEPTH` | `3` | Profondeur max de deep-dive |
| `MAX_SOURCES_PER_QUERY` | `8` | URLs max par sous-question |
| `MAX_SUB_QUERIES` | `7` | Sous-questions max |
| `OBSCURA_BIN` | `obscura` | Chemin vers le binaire Obscura |
| `OBSCURA_PORT` | `9222` | Port du serveur CDP Obscura |

---

## Architecture

```
deep-researcher/
├── researcher.py        # Moteur MSDR (query expand, recursive search, synthesis)
├── scraper.py           # Dual-layer scraper (Obscura + httpx fallback)
├── extractor.py         # Content extractor (Readability-alike, HTML->text)
├── server.py            # CLI + API server (Flask)
├── config/__init__.py   # Configuration
├── storage/
│   ├── reports/         # Rapports generes (JSON)
│   └── cache/           # Cache des pages scrapees
├── requirements.txt     # httpx, flask, beautifulsoup4, aiofiles
└── .gitignore
```

**Requiert aussi :** [france-student-bridge](https://github.com/Yormede/france-student-bridge) pour acceder aux LLMs

---

## Avertissement

> Ce projet peut cesser de fonctionner si France Student modifie son API.
> Respecte les rate limits — espace tes requetes d'au moins 5 secondes.
> Obscura necessite un binaire compile compatible avec ta plateforme (x86_64, ARM64).
>
> N'utilise pas ce projet pour du scraping abusif ou illegal.

---

## Licence

MIT. Si tu aimes le projet, laisse une etoile.

<p align="center">
  <a href="https://github.com/Yormede/deep-researcher">
    <img src="https://img.shields.io/github/stars/Yormede/deep-researcher?style=social" />
  </a>
</p>
