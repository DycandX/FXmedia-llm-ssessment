import os
import time
import logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
import chromadb

# Load env variables from .env relative to this file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vector_db")

# Configure Gemini API Key globally if present
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)

# Configure Gemini Embedding Model
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")

# Global variables for ChromaDB
chroma_client = None
collection = None

# Sample documents to ingest on startup
ML_DOCUMENTS = [
    {
        "id": "doc1",
        "text": "Supervised learning is a type of machine learning where the model is trained on labeled data, meaning each training example is paired with an output label to guide learning.",
        "metadata": {"title": "Supervised Learning", "source": "ML Basics 101"}
    },
    {
        "id": "doc2",
        "text": "Unsupervised learning is a branch of machine learning that analyzes and clusters unlabeled datasets, finding hidden patterns, features, or data groupings without human supervision.",
        "metadata": {"title": "Unsupervised Learning", "source": "ML Basics 101"}
    },
    {
        "id": "doc3",
        "text": "Reinforcement learning is an area of machine learning concerned with how intelligent agents ought to take actions in an environment to maximize cumulative reward over time.",
        "metadata": {"title": "Reinforcement Learning", "source": "Advanced AI Concepts"}
    },
    {
        "id": "doc4",
        "text": "Neural networks are computational models inspired by the human brain's neural structure, consisting of interconnected layers of nodes (neurons) that process and analyze data.",
        "metadata": {"title": "Neural Networks & Deep Learning", "source": "Deep Learning Intro"}
    },
    {
        "id": "doc5",
        "text": "Overfitting occurs when a machine learning model learns the training data too well, capturing noise and detail that do not generalize to new, unseen validation datasets.",
        "metadata": {"title": "Model Generalization & Overfitting", "source": "Practical ML Guide"}
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global chroma_client, collection
    
    current_key = os.getenv("GEMINI_API_KEY")
    if not current_key or current_key == "your_gemini_api_key_here":
        logger.critical("GEMINI_API_KEY is not configured in .env. Startup ingestion will be skipped.")
        yield
        return
        
    try:
        # Initialize Google GenAI configuration
        genai.configure(api_key=current_key)
        
        # Setup local persistent ChromaDB client
        db_path = Path(__file__).parent / "chroma_db"
        logger.info(f"Initializing persistent ChromaDB client at: {db_path.absolute()}")
        chroma_client = chromadb.PersistentClient(path=str(db_path.absolute()))
        
        # Create or recreate collection to ensure clean sample ingestion
        try:
            chroma_client.delete_collection(name="ml_docs")
            logger.info("Deleted existing 'ml_docs' collection for a clean ingestion.")
        except Exception:
            logger.info("Collection 'ml_docs' did not exist yet (starting fresh).")
            
        collection = chroma_client.create_collection(
            name="ml_docs",
            metadata={"hnsw:space": "cosine"}  # Use Cosine distance metric
        )
        
        # Generate embeddings and ingest documents
        logger.info("Generating embeddings and ingesting documents into ChromaDB...")
        ids = []
        documents = []
        metadatas = []
        embeddings = []
        
        for doc in ML_DOCUMENTS:
            # Call embedding API for each document
            res = genai.embed_content(
                model=EMBED_MODEL,
                content=doc["text"],
                task_type="retrieval_document"
            )
            embeddings.append(res["embedding"])
            ids.append(doc["id"])
            documents.append(doc["text"])
            metadatas.append(doc["metadata"])
            
        # Add to ChromaDB
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        logger.info(f"Successfully ingested {len(ids)} documents into ChromaDB.")
        
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

class SearchRequest(BaseModel):
    query: str = Field(..., description="The query string to search for similar documents", min_length=1)

class SearchResultItem(BaseModel):
    text: str = Field(..., description="The document text content")
    score: float = Field(..., description="The similarity/distance score (cosine distance)")
    metadata: dict = Field(..., description="The associated document metadata")

class SearchResponse(BaseModel):
    query: str = Field(..., description="The original search query")
    results: list[SearchResultItem] = Field(..., description="List of top 3 matching documents")

@app.post("/api/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    global collection
    
    if not collection:
        logger.error("Search failed: ChromaDB collection 'ml_docs' is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector database or API has not been initialized. Please configure GEMINI_API_KEY."
        )
        
    current_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=current_key)
    
    query = request.query
    logger.info(f"Incoming Search Request - Query: {query}")
    
    start_time = time.time()
    try:
        # 1. Generate embedding for query
        embed_start = time.time()
        res = genai.embed_content(
            model=EMBED_MODEL,
            content=query,
            task_type="retrieval_query"
        )
        query_embedding = res["embedding"]
        embed_duration = time.time() - embed_start
        
        # 2. Query ChromaDB with generated embedding
        db_start = time.time()
        db_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        db_duration = time.time() - db_start
        total_duration = time.time() - start_time
        
        logger.info(
            f"Query processed - Embedding time: {embed_duration:.2f}s | "
            f"ChromaDB Query time: {db_duration:.2f}s | Total: {total_duration:.2f}s"
        )
        
        # 3. Format response
        formatted_results = []
        if db_results and db_results["documents"]:
            docs = db_results["documents"][0]
            metas = db_results["metadatas"][0]
            distances = db_results["distances"][0]
            
            for i in range(len(docs)):
                formatted_results.append(
                    SearchResultItem(
                        text=docs[i],
                        score=distances[i],
                        metadata=metas[i]
                    )
                )
                
        logger.info(f"Returning {len(formatted_results)} results for query: {query}")
        return SearchResponse(query=query, results=formatted_results)
        
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

# Health check and DB statistics endpoint
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
