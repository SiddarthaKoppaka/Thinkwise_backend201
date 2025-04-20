from fastapi import APIRouter, HTTPException
from .models import UserRegister, UserLogin, Token
from .utils import hash_password, verify_password, create_token
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter()
MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
user_collection = client["thinkwise"]["users"]

@router.post("/register")
async def register(user: UserRegister):
    if await user_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    await user_collection.insert_one({
        "email": user.email,
        "hashed_password": hash_password(user.password)
    })
    return {"message": "User created"}

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    db_user = await user_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_token(str(db_user["_id"])))
