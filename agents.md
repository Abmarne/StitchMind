# AI Agent Instructions for StitchMind

Welcome, AI Agent! This file contains the core context, tech stack, and architectural guidelines for the StitchMind codebase. Please read and adhere to these rules when analyzing or modifying the repository.

## 1. Project Context

**StitchMind** is a local-first AI context stitcher. It acts as an assistant that gathers fragmented context from work tools (like Slack, Jira, GitHub, Gmail, and Google Docs), links related items, and presents unified, actionable "Context Cards" to the user.

- **Primary Goal**: Reduce the manual effort of reconstructing stories and timelines across different platforms.
- **Key Philosophy**: Zero-investment portfolio project. It must run locally without requiring paid external cloud databases or mandatory paid LLMs (it supports local Ollama).

## 2. Tech Stack

### Backend
- **Framework**: Python 3.10+, FastAPI, Uvicorn
- **Data Validation**: Pydantic
- **Relational DB**: SQLite (via SQLAlchemy)
- **Vector DB**: LanceDB (Local)
- **Embeddings**: SentenceTransformers
- **LLM Routing**: LiteLLM (supports Google Gemini and local Ollama)

### Frontend
- **Framework**: React 18+, Vite
- **Language**: TypeScript
- **Styling**: Vanilla CSS Modules (Do NOT use TailwindCSS or utility classes unless explicitly requested)
- **Icons**: `lucide-react`

## 3. Architectural Rules

1. **Local-First Mandate**: 
   - All data MUST be stored locally. 
   - Relational metadata goes into the local SQLite database.
   - Vector embeddings go into the local LanceDB store.
   - Do NOT introduce external database dependencies (e.g., PostgreSQL, MongoDB, Pinecone).
2. **Entity Linking**: 
   - Maintain the separation between **Deterministic Linking** (via Regex for Jira keys, PRs, URLs) and **Semantic Linking** (via Vector Similarity).
3. **Privacy by Default**: 
   - Connector configurations must be encrypted before storage (`app.crypto`).
   - The app must work without telemetry.
4. **Frontend Aesthetics**: 
   - Maintain a premium, rich design aesthetic. 
   - Use CSS Modules. Do not introduce inline styles for complex layouts.
   - Support both Dark and Light themes via CSS variables (`data-theme`).

## 4. Development Workflow

**Backend**:
```powershell
cd backend
# Create/activate virtual environment
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
*API Docs available at: `http://localhost:8000/docs`*

**Frontend**:
```powershell
cd frontend
npm install
npm run dev
```
*UI available at: `http://localhost:5173`*
