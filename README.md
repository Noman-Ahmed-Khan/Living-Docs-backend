# Living Docs Backend

A production-ready AI documentation system with explainable RAG and precise citations.

## Features
- Multi-tenant architecture (User -> Projects -> Documents)
- JWT-based authentication
- Document ingestion for PDF, DOCX, PPTX, XLSX, MD, HTML
- Character-level citation tracking
- RAG pipeline using LangChain, Google Gemini, and Pinecone

## Prerequisites
- Python 3.11+
- Google Gemini API Key
- Pinecone API Key and Index (1536 dimensions for Gemini embeddings)

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_INDEX_NAME=your_pinecone_index_name
   SECRET_KEY=your_secret_key_for_jwt
   DATABASE_URL=sqlite:///./living_docs.db
   ```

3. **Run the Application**
   ```bash
   uvicorn app.main:app --reload
   ```

## API Documentation
Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Ingestion Pipeline
1. **Upload**: Files are saved to the `uploads/` directory.
2. **Load**: `DocumentLoader` extracts text from various file formats.
3. **Chunk**: `Chunker` splits text into 1000-character segments with 100-character overlap, preserving offsets.
4. **Embed**: `GoogleGenerativeAIEmbeddings` generates vectors.
5. **Store**: Vectors are stored in Pinecone using the `project_id` as the namespace.

## Query Pipeline
1. **Retrieve**: Similarity search in Pinecone within the project's namespace.
2. **Prompt**: System prompt enforces strict context-only answering and citation format.
3. **Answer**: Gemini generates the response with embedded chunk IDs.
4. **Citations**: Metadata for all retrieved chunks is returned for frontend highlighting.
