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

# 1. Global Configuration
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api_wrapper")

# Configure Google Gemini API key globally
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    logger.critical("GEMINI_API_KEY is not set or using placeholder in .env file.")
else:
    genai.configure(api_key=api_key)

# 2. Lifespan (Startup API Key Validation)
@asynccontextmanager
async def lifespan(app: FastAPI):
    if api_key and api_key != "your_gemini_api_key_here":
        try:
            # Perform a lightweight API call on startup to validate key permissions
            genai.list_models()
            logger.info("Google Gemini API key successfully validated on startup.")
        except Exception as e:
            logger.error(f"Failed to validate API key at startup: {e}")
    yield

app = FastAPI(
    title="LLM API Wrapper Service",
    description="FastAPI Wrapper for Google Gemini API (gemini-2.5-flash)",
    version="1.0.0",
    lifespan=lifespan
)

# 3. Request & Response Schemas
class AskRequest(BaseModel):
    question: str = Field(..., description="The question/prompt to send to the Gemini model", min_length=1)

class AskResponse(BaseModel):
    answer: str = Field(..., description="The generated response from the Gemini model")

# 4. Endpoints
@app.post("/api/ask", response_model=AskResponse)
async def ask_gemini(request: AskRequest):
    # Reject request early if API Key is not set
    if not api_key or api_key == "your_gemini_api_key_here":
        logger.error("Request rejected: GEMINI_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is not configured on the server. Please check the .env file."
        )

    # Logging on request entry
    prompt = request.question
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    timestamp = datetime.utcnow().isoformat() + "Z"
    logger.info(f"Incoming Request - Timestamp: {timestamp} | Model: {model_name} | Prompt: {prompt}")

    start_time = time.time()
    try:
        # Enforce concise responses via system instructions
        system_instruction = (
            "You are a helpful, professional, and concise technical assistant. "
            "Provide clear, direct, and short answers. Avoid overly long explanations "
            "unless explicitly asked. Use clean formatting."
        )
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        
        if not response.text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Empty response received from the generative model."
            )
            
        # Logging latency only on successful response
        duration = time.time() - start_time
        logger.info(f"Successful Response - Duration: {duration:.2f}s | Response: {response.text[:100]}...")
        
        return AskResponse(answer=response.text)

    # Consolidated exception blocks
    except exceptions.InvalidArgument as e:
        logger.error(f"Invalid Argument Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid prompt or argument: {str(e)}"
        )
    except (exceptions.Unauthenticated, exceptions.PermissionDenied) as e:
        logger.error(f"Authentication/Permission Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. The provided API key might be invalid, restricted, or expired."
        )
    except exceptions.ResourceExhausted as e:
        logger.error(f"Rate Limit Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit or quota exceeded for the Gemini API. Please try again later."
        )
    except exceptions.GoogleAPICallError as e:
        logger.error(f"Google API Call Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error communicating with Google Gemini API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(e)}"
        )

@app.get("/health")
async def health_check():
    key_configured = api_key is not None and api_key != "your_gemini_api_key_here"
    return {
        "status": "healthy",
        "api_key_configured": key_configured
    }
