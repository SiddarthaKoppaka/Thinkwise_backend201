# src/main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.db     import db
from src.auth.routes import router as auth_router
from src.auth.password import router as pwd_router
from src.api.routes_analysis import router as analysis_router
from src.api.routes_chat     import router as chat_router
from src.api.routes_ideas    import router as ideas_router

app = FastAPI(
    title="Thinkwise Idea Analysis API",
    version="1.0.0"
)

origins = [
  "https://thinkwiseai-1w33ej9h0-siddarthakoppakas-projects.vercel.app",
  "https://thinkwiseai.vercel.app"
  # add any other domains you need (e.g. localhost for dev)
]

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Auth
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(pwd_router)

# Core API
app.include_router(chat_router)
app.include_router(analysis_router)
app.include_router(ideas_router)
