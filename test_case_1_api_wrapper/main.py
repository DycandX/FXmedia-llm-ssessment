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

# Load env variables from .env relative to this file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api_wrapper")

# Configure Gemini API Key globally if present
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform non-blocking API key validation at startup
    current_key = os.getenv("GEMINI_API_KEY")
    if not current_key or current_key == "your_gemini_api_key_here":
        logger.critical(
            "GEMINI_API_KEY is missing or using placeholder in .env. "
            "Please update the .env file with a valid Google Gemini API Key."
        )
    else:
        try:
            # Re-configure to ensure correctness
            genai.configure(api_key=current_key)
            # Try a lightweight API call to validate the key
            genai.list_models()
            logger.info("Google Gemini API key successfully validated on startup.")
        except exceptions.InvalidArgument as e:
            logger.critical(f"Google Gemini API key is invalid: {e}")
        except exceptions.Unauthenticated as e:
            logger.critical(f"Google Gemini API authentication failed: {e}")
        except Exception as e:
            logger.critical(f"Failed to validate API key at startup: {e}")
    yield

app = FastAPI(
    title="LLM API Wrapper Service",
    description="FastAPI Wrapper for Google Gemini API (gemini-2.5-flash)",
    version="1.0.0",
    lifespan=lifespan
)

class AskRequest(BaseModel):
    question: str = Field(..., description="The question/prompt to send to the Gemini model", min_length=1)

class AskResponse(BaseModel):
    answer: str = Field(..., description="The generated response from the Gemini model")

@app.post("/api/ask", response_model=AskResponse)
async def ask_gemini(request: AskRequest):
    current_key = os.getenv("GEMINI_API_KEY")
    if not current_key or current_key == "your_gemini_api_key_here":
        logger.error("Request rejected: GEMINI_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is not configured on the server. Please check the .env file."
        )

    # Configure genai with current key (handles dynamic updates to .env without server restart)
    genai.configure(api_key=current_key)

    # Structured request logging
    prompt = request.question
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    logger.info(f"Incoming Request - Timestamp: {timestamp} | Model: {model_name} | Prompt: {prompt}")

    start_time = time.time()
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        # Verify response content exists
        if not response.text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Empty response received from the generative model."
            )
            
        duration = time.time() - start_time
        logger.info(f"Successful Response - Duration: {duration:.2f}s | Response: {response.text[:100]}...")
        
        return AskResponse(answer=response.text)

    except exceptions.InvalidArgument as e:
        duration = time.time() - start_time
        logger.error(f"Invalid Argument Error - Duration: {duration:.2f}s | Detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid prompt or argument: {str(e)}"
        )
    except (exceptions.Unauthenticated, exceptions.PermissionDenied) as e:
        duration = time.time() - start_time
        logger.error(f"Authentication/Permission Error - Duration: {duration:.2f}s | Detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. The provided API key might be invalid, restricted, or expired."
        )
    except exceptions.ResourceExhausted as e:
        duration = time.time() - start_time
        logger.error(f"Rate Limit Error - Duration: {duration:.2f}s | Detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit or quota exceeded for the Gemini API. Please try again later."
        )
    except exceptions.GoogleAPICallError as e:
        duration = time.time() - start_time
        logger.error(f"Google API Call Error - Duration: {duration:.2f}s | Detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error communicating with Google Gemini API: {str(e)}"
        )
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Unexpected Error - Duration: {duration:.2f}s | Detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(e)}"
        )

# Health check and diagnostic endpoint
@app.get("/health")
async def health_check():
    current_key = os.getenv("GEMINI_API_KEY")
    key_configured = current_key is not None and current_key != "your_gemini_api_key_here"
    return {
        "status": "healthy",
        "api_key_configured": key_configured
    }
