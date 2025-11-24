from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.core.auth import (
    AuthMiddleware,
    CognitoAuthenticator,
    NotFoundExceptionHandler,
)
from app.routers import convert, s3
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    # Regex for App Runner and local dev URLs only
    allow_origin_regex=r"https://[a-z0-9]+\.[a-z0-9\-]+\.awsapprunner\.com|.*localhost.*|127\.0\.0\.1$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

authenticator = CognitoAuthenticator()
app.add_middleware(AuthMiddleware, authenticator=authenticator)
app.add_exception_handler(404, NotFoundExceptionHandler(authenticator))

app.include_router(convert.router)
app.include_router(s3.router)


@app.get("/health")
async def health():
    return {"detail": "ok"}, 200
