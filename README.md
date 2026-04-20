# Living Docs Backend

A production-ready AI documentation system with explainable RAG and precise citations.

## Purpose

**Living Docs** is an AI-powered document intelligence system with **RAG (Retrieval-Augmented Generation)** capabilities. It enables users to:
- Upload documents in 7 formats (PDF, DOCX, PPTX, XLSX, MD, TXT, HTML)
- Process documents through a sophisticated chunking & embedding pipeline
- Query documents using natural language with precise character-level citations
- Maintain multi-turn conversations with document context

## Architecture

The project follows **Domain-Driven Design (DDD)** with **Clean Architecture** principles:

```
Presentation (API) → Application (Services) → Domain (Business Logic) ← Infrastructure (External I/O)
```

## Features

- **Multi-tenant architecture** - User → Projects → Documents → Chat Sessions
- **JWT-based authentication** with refresh token rotation and account lockout
- **Document ingestion** for 7 file formats with intelligent chunking
- **Character-level citation tracking** with source metadata (file, page, offset)
- **RAG pipeline** using LangChain, Hugging Face embeddings, and Pinecone
- **Multi-turn conversations** with persistent chat history and context awareness
- **RESTful API** with OpenAPI/Swagger documentation
- **Comprehensive error handling** with standardized responses
- **Unit testing** with pytest, with E2E coverage planned

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Hugging Face API Key
- Pinecone API Key and Index (384 dimensions for Hugging Face embeddings)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/living_docs

# External APIs
HUGGINGFACE_API_KEY=your_hf_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_pinecone_index_name

# Security
SECRET_KEY=your_secret_key_for_jwt_tokens
```

### 3. Database Setup
```bash
# Run migrations
alembic upgrade head
```

### 4. Run the Application
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs` (interactive testing)
- **ReDoc**: `http://localhost:8000/redoc` (clean reference)
- **OpenAPI JSON**: `http://localhost:8000/api/v1/openapi.json` (machine-readable)

### Documentation Files

- **[documentation/API_DOCUMENTATION.md](documentation/API_DOCUMENTATION.md)** - Comprehensive API reference with examples
- **[documentation/API_QUICK_REFERENCE.md](documentation/API_QUICK_REFERENCE.md)** - Quick lookup table for all endpoints
- **[documentation/SWAGGER_GUIDE.md](documentation/SWAGGER_GUIDE.md)** - Guide to using interactive Swagger
- **[documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md)** - System architecture and design patterns
- **[documentation/FILE_PROCESSING_AND_QUERY_WORKFLOW.md](documentation/FILE_PROCESSING_AND_QUERY_WORKFLOW.md)** - RAG pipeline walkthrough

## Project Structure

```
backend/
├── alembic/                          # Database migrations
├── app/
│   ├── api/                          # Presentation Layer (REST endpoints)
│   │   ├── auth.py, users.py, projects.py, documents.py, query.py, chat.py
│   │   ├── schemas/                  # Pydantic models for validation
│   │   └── middleware/               # Error handling & middleware
│   ├── application/                  # Application Layer (Use case orchestration)
│   │   ├── auth/, users/, projects/, documents/, query/, chat/
│   │   └── service.py & dto.py in each module
│   ├── domain/                       # Domain Layer (Business logic)
│   │   ├── chat/, documents/, projects/, users/, rag/
│   │   ├── entities.py, interfaces.py, exceptions.py
│   ├── infrastructure/               # Infrastructure Layer (External I/O)
│   │   ├── database/                 # PostgreSQL + SQLAlchemy
│   │   ├── storage/                  # File storage
│   │   ├── rag/                      # LangChain, embeddings, vectorstore
│   │   ├── security/                 # JWT, password hashing
│   │   ├── email/                    # Email services
│   │   └── tasks/                    # Background task processing
│   ├── config/                       # Configuration & constants
│   └── templates/                    # Email templates
├── tests/
│   ├── unit/                         # Unit tests
│   └── e2e/                          # End-to-end tests
├── scripts/                          # Utility scripts
├── documentation/                    # API & architecture docs
└── requirements.txt
```

> Note: the current test suite is `tests/unit/`; end-to-end coverage is still planned.

## Data Model

The system uses the following core entities:

- **User**: Authentication credentials, profile, security settings
- **Project**: Container for documents & conversations (single owner)
- **Document**: Uploaded files with processing status and metadata
- **ChatSession**: Multi-turn conversation within a project context
- **ChatMessage**: Individual messages with role (user/assistant/system)

Entity relationships:
```
User → owns many → Projects
Project → contains many → Documents
Project → contains many → ChatSessions → contains many → ChatMessages
```

## Data Flows

### Document Ingestion Pipeline
1. **Upload**: File saved to `uploads/{project_id}/`
2. **Parse**: LangChain loads document based on format
3. **Chunk**: RecursiveCharacterTextSplitter (1000 char chunks, 200 overlap)
4. **Embed**: HuggingFace embeddings (384-768 dimensions)
5. **Store**: Chunks indexed in Pinecone with project namespace
6. **Track**: Document status updated to COMPLETED

### Query & Citation Flow
1. **Retrieve**: Query embedded and searched against Pinecone
2. **Context**: Prior chat messages included for multi-turn understanding
3. **Generate**: LLM builds context and generates answer
4. **Cite**: Auto-extract chunk IDs from answer with metadata
5. **Store**: Save Q&A to chat history for context tracking
6. **Return**: Answer with citations, source metadata, and tracking info

## Core Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API** | FastAPI | REST endpoints with automatic OpenAPI spec |
| **Database** | PostgreSQL + SQLAlchemy | Persistent data storage & ORM |
| **Migrations** | Alembic | Schema versioning |
| **Vector DB** | Pinecone | Semantic search at scale |
| **Embeddings** | HuggingFace | Text-to-vector conversion |
| **LLM** | HuggingFace | Answer generation |
| **Text Processing** | LangChain | Document loading & chunking |
| **Authentication** | python-jose + bcrypt | JWT + password security |
| **Email** | aiosmtplib | Async email verification |
| **Testing** | pytest | Unit test framework |

## TODO / Next Steps

The core API, RAG flow, and document lifecycle are in place. The main gaps I would prioritize next are:

- Add Redis + Celery to move document ingestion and re-ingestion out of FastAPI `BackgroundTasks` into durable jobs with retries and progress tracking.
- Add a dedicated `redis` service and worker service in `docker-compose.yml` so background processing can run independently of the API process.
- Add Redis-backed caching and rate limiting for hot paths like auth, project lookups, and repeated queries.
- Add S3/MinIO-style object storage instead of local-only `uploads/` to make file storage production-safe.
- Add end-to-end and integration tests for auth, upload -> ingest -> query, delete, and reingestion flows. The current suite is mostly unit tests.
- Add observability: structured request logs, metrics, tracing, and error tracking.

## Key Endpoints

### Authentication (`/api/v1/auth`)
- `POST /register` - Register new user with email verification
- `POST /login` - Get JWT access token + refresh token
- `POST /refresh` - Refresh expired access token
- `POST /verify-email` - Verify email with token

### Projects (`/api/v1/projects`)
- `GET /` - List user's projects
- `POST /` - Create new project
- `GET /{id}` - Get project details
- `PATCH /{id}` - Update project
- `DELETE /{id}` - Delete project

### Documents (`/api/v1/documents`)
- `POST /upload` - Upload documents to project
- `GET /{id}` - Get document metadata & status
- `GET /{id}/download` - Download original document file
- `DELETE /{id}` - Remove document

### Query (`/api/v1/query`)
- `POST /` - Submit natural language query with RAG
- `GET /history` - Retrieve past query history

### Chat Sessions (`/api/v1/chat`)
- `POST /sessions` - Create new chat session
- `PATCH /sessions/{id}` - Update session (rename, archive)
- `GET /sessions` - List active sessions
- `DELETE /sessions/{id}` - Delete session
