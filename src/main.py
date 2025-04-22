import os
import io
import json
import datetime
import traceback
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from collections import defaultdict
from dateutil import parser

from src.core.db import db, collection  
from src.api.routes_analysis import router as analysis_router
from src.auth.dependencies import get_current_user
from src.auth.routes import router as auth_router
from src.api.routes_chat import router as chat_router
from src.api.routes_ideas import router as ideas_router

# FastAPI instance
app = FastAPI(title="Thinkwise Idea Analysis API", version="1.0.0")

# Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth")
app.include_router(chat_router)
app.include_router(analysis_router)
app.include_router(ideas_router)
