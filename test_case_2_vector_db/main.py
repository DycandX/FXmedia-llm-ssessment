import os
import time
import logging
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
import chromadb

# 1. Global Configuration
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vector_db")

# Configure Gemini API Key and Model globally
api_key = os.getenv("GEMINI_API_KEY")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")

if not api_key or api_key == "your_gemini_api_key_here":
    logger.critical("GEMINI_API_KEY is not set or using placeholder in .env file.")
else:
    genai.configure(api_key=api_key)

# Global variables for ChromaDB
chroma_client = None
collection = None

# 2. Database Ingestion & Lifespan Setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    global chroma_client, collection
    
    if not api_key or api_key == "your_gemini_api_key_here":
        logger.critical("GEMINI_API_KEY is missing. Ingestion skipped.")
        yield
        return
        
    try:
        # Step A: Load documents from external documents.json
        json_path = Path(__file__).parent / "documents.json"
        if not json_path.exists():
            logger.error(f"documents.json not found at: {json_path.absolute()}")
            yield
            return
            
        with open(json_path, "r", encoding="utf-8") as f:
            ml_documents = json.load(f)
            
        # Step B: Initialize Local Persistent ChromaDB Client
        db_path = Path(__file__).parent / "chroma_db"
        logger.info(f"Initializing persistent ChromaDB client at: {db_path.absolute()}")
        chroma_client = chromadb.PersistentClient(path=str(db_path.absolute()))
        
        # Step C: Get or Create 'ml_docs' Collection with Cosine Space
        collection = chroma_client.get_or_create_collection(
            name="ml_docs",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Step D: Ingestion & Indexing (only if collection is currently empty)
        doc_count = collection.count()
        if doc_count == 0:
            logger.info("ChromaDB collection is empty. Generating embeddings and ingesting documents...")
            ids, documents, metadatas, embeddings = [], [], [], []
            
            for doc in ml_documents:
                # Prepare metadata (title, source, category, keywords)
                meta = {
                    "title": doc["title"],
                    "source": doc["source"],
                    "category": doc["category"],
                    "keywords": ", ".join(doc["keywords"])
                }
                # Step E: Generate embeddings using task_type="retrieval_document"
                res = genai.embed_content(
                    model=EMBED_MODEL,
                    content=doc["content"],
                    task_type="retrieval_document"
                )
                embeddings.append(res["embedding"])
                ids.append(doc["id"])
                documents.append(doc["content"])
                metadatas.append(meta)
                
            # Insert into ChromaDB collection
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Successfully ingested {len(ids)} documents into ChromaDB.")
        else:
            logger.info(f"ChromaDB collection 'ml_docs' already initialized with {doc_count} documents. Skipping ingestion.")
            
    except exceptions.GoogleAPICallError as e:
        logger.critical(f"Google Gemini API error during startup ingestion: {e}")
    except Exception as e:
        logger.critical(f"Unexpected error during startup: {e}")
        
    yield

app = FastAPI(
    title="Vector Database Integration Service",
    description="FastAPI service integrated with ChromaDB and Gemini Embedding (text-embedding-004)",
    version="1.0.0",
    lifespan=lifespan
)

# 3. Request & Response Schemas
class SearchRequest(BaseModel):
    query: str = Field(..., description="The query string to search for similar documents", min_length=1)

class SearchResultItem(BaseModel):
    text: str = Field(..., description="The document text content")
    score: float = Field(..., description="The similarity score (cosine similarity, 1.0 - distance)")
    metadata: dict = Field(..., description="The associated document metadata (title, source, etc.)")

class SearchResponse(BaseModel):
    query: str = Field(..., description="The original search query")
    results: list[SearchResultItem] = Field(..., description="List of top 3 matching documents")

# 4. Endpoints
@app.post("/api/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    global collection
    
    if not collection:
        logger.error("Search failed: ChromaDB collection 'ml_docs' is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database or API has not been initialized. Please configure GEMINI_API_KEY."
        )
        
    query = request.query
    logger.info(f"Incoming Search Request - Query: {query}")
    
    start_time = time.time()
    try:
        # Step F: Generate query embedding using task_type="retrieval_query"
        embed_start = time.time()
        res = genai.embed_content(
            model=EMBED_MODEL,
            content=query,
            task_type="retrieval_query"
        )
        query_embedding = res["embedding"]
        embed_duration = time.time() - embed_start
        
        # Step G: Query ChromaDB for top 3 matches
        db_start = time.time()
        db_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        db_duration = time.time() - db_start
        total_duration = time.time() - start_time
        
        logger.info(
            f"Query processed - Embedding: {embed_duration:.2f}s | "
            f"ChromaDB Query: {db_duration:.2f}s | Total Latency: {total_duration:.2f}s"
        )
        
        # Step H: Format results and convert cosine distance to cosine similarity
        formatted_results = []
        if db_results and db_results["documents"]:
            docs = db_results["documents"][0]
            metas = db_results["metadatas"][0]
            distances = db_results["distances"][0]
            
            for i in range(len(docs)):
                # Convert cosine distance to cosine similarity (1.0 - distance)
                similarity_score = round(1.0 - distances[i], 4)
                formatted_results.append(
                    SearchResultItem(
                        text=docs[i],
                        score=similarity_score,
                        metadata=metas[i]
                    )
                )
                
        logger.info(f"Returning {len(formatted_results)} results for query: {query}")
        return SearchResponse(query=query, results=formatted_results)
        
    # Consolidated exception blocks
    except exceptions.InvalidArgument as e:
        logger.error(f"Invalid Argument error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Embedding API error: {str(e)}"
        )
    except (exceptions.Unauthenticated, exceptions.PermissionDenied) as e:
        logger.error(f"Authentication/Permission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication failed. Verify that GEMINI_API_KEY is valid."
        )
    except exceptions.ResourceExhausted as e:
        logger.error(f"Rate Limit error: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API rate limit exceeded."
        )
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(e)}"
        )

@app.get("/health")
async def health_check():
    key_configured = api_key is not None and api_key != "your_gemini_api_key_here"
    db_initialized = collection is not None
    doc_count = collection.count() if db_initialized else 0
    return {
        "status": "healthy",
        "api_key_configured": key_configured,
        "database_initialized": db_initialized,
        "document_count": doc_count
    }
