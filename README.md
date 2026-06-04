# StitchMind: AI Context Stitcher 🧠🔗

StitchMind is an intelligent, **local-first** developer assistant that reduces cognitive load by automatically gathering fragmented context across Slack, Jira, GitHub, Gmail, and Google Docs, presenting them as unified, actionable visual cards and mapping them onto an interactive knowledge graph.

Built as a **zero-investment, portfolio-grade project**, StitchMind runs entirely on your local machine—preserving 100% data privacy and incurring no hosting costs.

---

## 🚀 Key Features

* **Conversational Slack Thread Grouping**: Instead of indexing single-line, disconnected messages, StitchMind groups adjacent Slack chats and nested threads into cohesive conversational logs, providing rich semantic context for RAG.
* **Deterministic & Semantic Linking**: Employs regex rules for hard pattern links (e.g. mapping Jira keys like `PROJ-102` or GitHub PR numbers) alongside Sentence-Transformers vector similarity checks in LanceDB.
* **Interactive Force-Directed SVG Graph**: Visualizes document links as a real-time, animated cluster graph using a custom physics engine running natively on an SVG canvas (no heavy chart library dependencies).
* **Dual-Engine LLM Core**: Configurable wrapper supporting **Google Gemini 1.5 Flash** (via a free API key) for fast cloud processing, or **Ollama** (e.g. Llama-3, Phi-3) for 100% offline execution.
* **Demo Sandbox Seeding**: Ready to test out-of-the-box! Clicking the "Seed Sandbox" button instantly populates SQLite and LanceDB with realistic cross-platform items relating to a session-refresh bug.

---

## 🛠️ Technology Stack

* **Backend**: FastAPI (Python 3.10+), SQLAlchemy + Uvicorn.
* **Databases**: SQLite (metadata, relationships, configurations) & LanceDB (local vector storage).
* **AI/ML Orchestration**: LiteLLM, Sentence-Transformers (`all-MiniLM-L6-v2` running locally).
* **Frontend**: React (v19) + Vite + TypeScript.
* **Styling**: Vanilla CSS Modules (Glassmorphism layout, customized transitions, responsive layouts).

---

## 📂 Codebase Architecture

```text
StitchMind/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── connectors/       # Platform Ingestion modules (Slack, Jira, GitHub, Google)
│   │   ├── config.py         # Global settings & storage paths
│   │   ├── crypto.py         # Symmetric credentials encryption
│   │   ├── database.py       # SQLite engine and SQLAlchemy ORM models
│   │   ├── embedder.py       # Sentence-Transformers local wrapper
│   │   ├── main.py           # API endpoints (Connectors, Docs, Graph, Sandbox Seeder)
│   │   ├── pipeline.py       # Chunking, Regex linking, and LiteLLM unification
│   │   └── vector_store.py   # LanceDB client & schema definition
│   ├── requirements.txt
│   └── run.py                # Backend Uvicorn dev-start script
├── frontend/                 # React Application
│   ├── src/
│   │   ├── components/       # Layout, Card, ConnectionPanel, Graph
│   │   ├── services/         # Type-safe API client (api.ts)
│   │   ├── App.tsx           # Dashboard tab state router
│   │   ├── index.css         # Styling system & dark/light theme tokens
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── start-stitchmind.ps1      # Double-click startup orchestrator script
└── README.md
```

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.10+
* Node.js v18+ & npm

### Windows Fast Boot
1. Clone the repository and navigate to the project directory.
2. Open a PowerShell terminal and execute the boot script:
   ```powershell
   .\start-stitchmind.ps1
   ```
This will automatically launch the FastAPI server in one window and the Vite React server in another, opening `http://localhost:5173` in your browser.

---

## 🔑 Integrations Setup

To ingest real data, navigate to the **Connectors** page inside the Web UI:

* **GitHub**: Generate a Personal Access Token (PAT) with `repo` scopes and input the `owner/repository` name.
* **Slack**: Create a Slack Bot application, obtain a Bot User OAuth Token (`xoxb-`), join target channels, and enter their channel IDs.
* **Jira**: Generate a Jira API token, configure your Atlassian domain, and email login.
* **Google Workspace (Gmail / Docs)**:
  1. Create a Desktop application in Google Cloud Console.
  2. Grant **Gmail read** and **Drive read** scopes.
  3. Download the credentials JSON, rename it to `credentials.json`, and place it in the backend's data folder: `backend/data/credentials.json`.
  4. The sync script will automatically handle OAuth loopback via your local browser on your first sync trigger.
