# Living Docs Backend

A production-ready AI documentation backend with explainable RAG, precise citations, and a clean architecture.

![Architecture Diagram](documentation/architecture-diagram.jpg)

## Purpose

**Living Docs** is a document intelligence backend built to support:
- Secure multi-tenant projects with user-owned document libraries
- Document ingestion across multiple formats
- Retrieval-augmented query and chat over uploaded content
- Explicit source citations tied to chunk metadata and bounding boxes
- Persistent chat sessions with conversation-aware retrieval

## Architecture & Design

This repository is organized as a Clean Architecture / Domain-Driven Design system.

```
Presentation (FastAPI) → Application (Orchestration) → Domain (Entities + Interfaces)
                 ↑                                      ↓
           Infrastructure (DB, storage, RAG, auth, email)
```

### Layer mapping

- `app/api/` — HTTP layer, request validation, route definitions, middleware
- `app/application/` — business process orchestration and use-case services
- `app/domain/` — core entities, exceptions, interfaces, value objects, business rules
- `app/infrastructure/` — concrete implementations for database, file storage, RAG, security, email, and tasks
- `app/container.py` — composition root; the only place concrete implementations are wired to interfaces

### Key design principles

- Dependency inversion: services depend on interfaces, not concrete implementations
- Lazy initialization for RAG components: embeddings, vector store, and LLM are created only when needed
- Parent/child chunk hierarchy: parent chunks provide paragraph-level context while child chunks drive similarity search
- Project namespace isolation: Pinecone namespaces use the project ID, so each project is separated in the vector store
- Chat-aware retrieval: query service can include recent session history to resolve follow-up questions

## RAG Pipeline Overview

The RAG pipeline is implemented in code across the following areas:

- `app/application/documents/ingestion_service.py` — orchestrates upload ingestion
- `app/infrastructure/rag/chunkers/unstructured_chunker.py` — converts file text into parent/child chunks
- `app/infrastructure/rag/embeddings/huggingface_embedder.py` — generates embeddings with Hugging Face
- `app/infrastructure/rag/vectorstores/pinecone_store.py` — stores and searches vectors in Pinecone
- `app/application/query/query_service.py` — orchestrates retrieval, prompt construction, LLM generation, and citations
- `app/infrastructure/rag/retrievers/document_retriever.py` — retrieves child chunks and resolves parent context

### Document ingestion flow (code-level)

1. User uploads a document via `app/api/documents.py`.
2. `DocumentService` validates and persists document metadata.
3. `IngestionService.ingest_document()` reads the file from `LocalFileStore`.
4. `UnstructuredLayoutChunker` splits the document into a mixed list of parent and child `Chunk` entities.
   - Child chunks are suitable for semantic search.
   - Parent chunks are kept so the query pipeline can resolve broader paragraph context.
5. `HuggingFaceEmbedder.embed_batch()` converts every chunk text into embedding vectors.
6. `PineconeVectorStore.add_chunks()` stores all vectors with metadata keys like `document_id`, `chunk_id`, `page`, `chunk_type`, and bounding box fields.
7. Document status is updated via the document repository.

### Query / retrieval flow (code-level)

1. The query endpoint in `app/api/query.py` receives a natural language question.
2. `QueryService.query()` validates the request and optionally loads recent session history from `ChatRepository`.
3. The text query is transformed into an embedding by `HuggingFaceEmbedder.embed_text()`.
4. `DocumentRetriever.retrieve()` searches Pinecone for the top child chunks.
   - The default search strategy is similarity search.
   - The system can also use MMR for diversity if configured.
5. `BaseRetriever._resolve_parent_context()` fetches parent chunks by ID for any retrieved child chunk that includes `parent_id`.
6. `QueryService._format_context()` combines child text and parent context into a prompt section.
7. `HuggingFaceLLMClient.generate()` sends the assembled prompt to the LLM.
8. `QueryService._build_citations()` parses the model output, extracts chunk references, and attaches metadata such as file, page, and character offset.
9. The final `QueryResult` includes the generated answer, citation list, document sources, and diagnostics metadata.

## Features

- Secure JWT authentication with refresh token rotation
- Multi-project, multi-document workspace model
- File upload support for PDF, DOCX, PPTX, XLSX, MD, TXT, HTML
- Document ingestion with parent/child chunk structure
- Hugging Face embeddings and LLM for RAG
- Pinecone vector store with namespace and parent-child support
- Persistent chat sessions and message history
- Source-backed responses with citation metadata
- Clean error handling and API-standard response models

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Hugging Face API Key
- Pinecone API Key and Index

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
alembic upgrade head
```

### 4. Run the Application
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/api/v1/openapi.json`

### Documentation Files

- **[documentation/API_DOCUMENTATION.md](documentation/API_DOCUMENTATION.md)**
- **[documentation/API_QUICK_REFERENCE.md](documentation/API_QUICK_REFERENCE.md)**
- **[documentation/SWAGGER_GUIDE.md](documentation/SWAGGER_GUIDE.md)**
- **[documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md)**
- **[documentation/FILE_PROCESSING_AND_QUERY_WORKFLOW.md](documentation/FILE_PROCESSING_AND_QUERY_WORKFLOW.md)**

## Project Structure

```
backend/
├── alembic/
├── app/
│   ├── api/
│   ├── application/
│   ├── config/
│   ├── domain/
│   └── infrastructure/
├── tests/
├── scripts/
├── documentation/
└── requirements.txt
```

## Data Model

- **User**: owns projects and controls access
- **Project**: namespace for related documents and chat
- **Document**: uploaded file metadata, status, and chunk counts
- **ChatSession**: conversation state linked to a project
- **ChatMessage**: individual user/assistant messages

## RAG Pipeline Summary

### Ingestion
- Document file is saved to local storage
- Chunker splits text into structured chunks
- Embedder converts text to vectors
- Vector store upserts vectors into Pinecone
- Document status is updated

### Query
- Query is embedded
- Relevant chunks are retrieved from Pinecone
- Parent chunk context is resolved
- Prompt is built with document and chat context
- LLM generates an answer
- Citations are extracted and returned

## Core Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI | REST interface |
| Database | PostgreSQL + SQLAlchemy | Persistence |
| Vector DB | Pinecone | Semantic search |
| Embeddings | Hugging Face | Vector encoding |
| LLM | Hugging Face | Response generation |
| Chunking | LangChain / Unstructured | Document splitting |
| Auth | JWT + bcrypt | Security |
| Testing | pytest | Unit tests |

## Next Improvements

- Move ingestion into durable background jobs (Redis/Celery)
- Add production object storage instead of local filesystem
- Expand end-to-end test coverage
- Add observability, tracing, and metrics
- Harden Pinecone error handling and namespace cleanup

## Key Endpoints

### Authentication
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/verify-email`

### Projects
- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{id}`
- `PATCH /api/v1/projects/{id}`
- `DELETE /api/v1/projects/{id}`

### Documents
- `POST /api/v1/documents/upload`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/download`
- `DELETE /api/v1/documents/{id}`

### Query
- `POST /api/v1/query`
- `GET /api/v1/query/history`

### Chat
- `POST /api/v1/chat/sessions`
- `PATCH /api/v1/chat/sessions/{id}`
- `GET /api/v1/chat/sessions`
- `DELETE /api/v1/chat/sessions/{id}`
