from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from .models import UserRegister, UserLogin, Token, UserProfile
from .utils import hash_password, verify_password, create_token
from motor.motor_asyncio import AsyncIOMotorClient
import os
from src.auth.dependencies import get_current_user
from src.core.config import settings
from .email import send_email


router = APIRouter()

MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
user_collection = client["thinkwise"]["users"]

@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister, background_tasks: BackgroundTasks):
    if await user_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    await user_collection.insert_one({
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "hashed_password": hash_password(user.password)
    })

    # 3) send welcome email in background
    background_tasks.add_task(
      send_email,
      subject="Welcome to Thinkwise!",
      recipients=[user.email],
      body=f"Hi {user.first_name},<br>Thanks for joining..."
    )

    return {
        "message": "User created",
        "user": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }

@router.post("/login")
async def login(user: UserLogin):
    db_user = await user_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({
        "sub": str(db_user["_id"]),
        "email": db_user["email"],
        "first_name": db_user.get("first_name", ""),
        "last_name": db_user.get("last_name", "")
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user["_id"]),
            "email": db_user["email"],
            "first_name": db_user.get("first_name", ""),
            "last_name": db_user.get("last_name", "")
        }
    }


@router.get("/me", response_model=UserProfile)
async def read_current_user(current_user: dict = Depends(get_current_user)):
    # current_user payload has sub,email,first_name,last_name
    return {
        "id": current_user["sub"],
        "email": current_user["email"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
    }
