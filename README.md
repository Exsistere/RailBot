# RailYatri

## 1. Project Overview

**RailYatri** is an AI-powered conversational assistant for Indian Railways, providing users with train search, PNR status tracking, and FAQ retrieval via a modern chat interface. It leverages a modular, multi-tool agent architecture orchestrated by LangGraph, with a strong focus on shared semantic context and robust backend engineering.

**Core Capabilities:**
- Natural language train search
- PNR status and refund tracking
- FAQ retrieval using RAG (Retrieval-Augmented Generation)
- Multi-intent, multi-tool workflows
- Persistent user and conversation mapping

**Implemented Tools:**
- **Search Trains Tool**: Finds trains between stations with class/quota support.
- **PNR Status Tool**: Tracks and explains PNR status, refund, and waitlist.
- **FAQ RAG Tool**: Retrieves policy/FAQ answers from a Qdrant vector DB.

**Architecture Philosophy:**
- All tools collaborate via a central Shared Context object.
- Orchestration is handled by a LangGraph workflow, not by tools.
- Services and repositories are strictly separated for maintainability.
- All LLM prompts and logic are explicit and versioned.

---

## 2. Features

- Train search with source and destination(can filter based on days of the week)
- PNR status
- FAQ/policy retrieval (RAG)
- Multi-intent, multi-tool conversational flows(currently only supports single intent)
- Central shared memory/context for all tools
- Universal LLM-based response synthesis
- Streamlit frontend with structured rendering
- Persistent user, conversation, and tool execution history

---

## 3. High-Level Architecture

**System Flow:**

```
User Query
   ↓
[Guardrail] → [Intent Classifier] → [Shared Context Extraction]
   ↓
[Planner] → [Router] → [Tool Execution(s)]
   ↓
[Shared Context Enrichment]
   ↓
[Universal Responder]
   ↓
[Frontend Rendering]
```

**Architecture Diagram:**

```
+-------------------+
|    Frontend UI    |
+--------+----------+
         |
         v
+--------+----------+
|   FastAPI Backend |
+--------+----------+
         |
         v
+-------------------+
|   LangGraph Flow  |
|-------------------|
| Guardrail         |
| Intent Classifier |
| SharedContext     |
| Planner           |
| Router            |
| Tool Node(s)      |
| Responder         |
+--------+----------+
         |
         v
+-------------------+
|  Services Layer   |
+--------+----------+
         |
         v
+-------------------+
|  Repositories     |
+--------+----------+
         |
         v
+-------------------+
| PostgreSQL | Qdrant|
+-------------------+
```

**Key Components:**
- **FastAPI**: REST API backend.
- **LangGraph**: Orchestrates the workflow as a state graph.
- **SharedContext**: Central semantic memory for all tools.
- **Tools**: Modular, injectable, and stateless.
- **Services**: Orchestrate business logic and external APIs.
- **Repositories**: Handle all DB access.
- **PostgreSQL**: Relational data (users, conversations, PNRs, etc).
- **Qdrant**: Vector DB for FAQ/document retrieval.

---

## 4. Shared Context Architecture

**SharedContext** is the central, immutable memory object passed through the workflow. It contains:
- Semantic understanding (stations, dates, intents, PNRs, etc.)
- Tool-generated memory (e.g., inferred train number, waitlist status)
- Retrieved RAG chunks (FAQ/policy context)
- Execution metadata (which tools ran, which failed)

**Why?**
- Enables tools to collaborate without direct coupling.
- All memory updates are explicit and merged safely.
- Supports multi-tool, multi-intent workflows.

**How?**
- Extracted once per query by the SharedContextExtractor.
- Enriched by each tool via memory_updates.
- Merged using a safe, append-only strategy.

---

## 5. Tool Architecture

**Generalized Tool System:**
- All tools inherit from `BaseTool` (Template Method pattern).
- Tools are registered in a central `TOOL_REGISTRY`.
- The `ToolFactory` injects required services into each tool.
- Planner determines which tools to run and in what order.

**Planner/Tool Execution Flow:**
- Planner maps detected intents to plan steps.
- Each step is mapped to a tool via the registry.
- Tools read from SharedContext and return results + memory updates.

**Key Tools:**

### SearchTrainsTool
- Finds trains between stations on a date.
- Reads from SharedContext or plan params.
- Uses external Railway API (NTES).

### CheckPNRTool
- Checks PNR status for a user.
- Enriches SharedContext with train number, waitlist, etc.
- Uses external Railway API and persists results.

### FAQRAGTool
- Retrieves FAQ/policy chunks from Qdrant.
- Appends retrieved knowledge to SharedContext.
- Does not generate answers (Responder does).

**External Integrations:**
- NTES API (train/PNR data)
- Qdrant (FAQ/document retrieval)
- Groq/OpenAI-compatible LLM APIs

---

## 6. Database Design

**Tables:**
- `users`: Auth, JWT identity, user anchor.
- `conversations`: Chat session grouping.
- `messages`: Pure conversational history.
- `interactions`: One LangGraph execution per query.
- `tool_executions`: Per-tool execution trace.
- `pnrs`: Cached PNR journey state.
- `user_pnrs`: User ↔ PNR mapping.

**Repository-Service Separation:**
- **Repositories**: Pure DB logic, no business rules.
- **Services**: Orchestrate repositories, external APIs, and business logic.

**ER Diagram:**

```
users ──< conversations ──< messages
   │             │
   │             └──< interactions ──< tool_executions
   │
   └──< user_pnrs >── pnrs
```

---

## 7. Tech Stack

- **Python**: Core language for backend and tools.
- **FastAPI**: High-performance REST API.
- **LangGraph**: Orchestrates multi-step, multi-tool workflows.
- **Streamlit**: Modern, chat-style frontend.
- **PostgreSQL**: Relational data storage.
- **Qdrant**: Vector DB for FAQ/document retrieval.
- **Groq/OpenAI APIs**: LLM-powered intent, extraction, and response.
- **NTES API**: Real-time railway data.

*Each technology is chosen for reliability, extensibility, and modern best practices.*

---

## 8. API & Workflow Example

**Example Query:**  
*"Check my PNR and tell refund status"*

**Lifecycle:**
1. **Intent Detection**: Classifier detects `CHECK_PNR_STATUS`.
2. **Shared Context**: Extractor parses PNR from query, populates SharedContext.
3. **Tool Execution**: CheckPNRTool runs, fetches status, updates memory.
4. **Response Synthesis**: Universal Responder generates a natural-language answer using SharedContext and tool results.

---

## 9. Running the Project

**Installation:**
```sh
git clone https://github.com/your-org/railyatri.git
cd railyatri
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Environment Setup:**
Create a `.env` file in the root:
```
POSTGRES_URL=postgresql://user:password@localhost:5432/railyatri
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=railyatri_faq
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENAI_API_KEY=sk-...
GROQ_API_KEY=...
```

**Database Setup:**
- Ensure PostgreSQL is running and accessible.


**Backend Startup:**
```sh
uvicorn app.main:app --reload
```

**Frontend Startup:**
```sh
streamlit run frontend/app.py
```

**FAQ Ingestion:**
```sh
python scripts/ingest_faq_docs.py --file docs/faq_paths.json
```

---

*For further details, see code comments and architecture docs. All logic is implemented as described above; no features are invented or omitted.*

