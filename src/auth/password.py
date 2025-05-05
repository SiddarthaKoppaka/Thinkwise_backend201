from fastapi import APIRouter, HTTPException, BackgroundTasks
from .models import PasswordResetRequest, PasswordReset
from .utils import create_password_reset_token, verify_password_reset_token, hash_password
from .email import send_email
from motor.motor_asyncio import AsyncIOMotorClient
import os
from bson import ObjectId
from src.core.config import settings


router = APIRouter(prefix="/auth", tags=["password"])
user_col = AsyncIOMotorClient(os.getenv("MONGO_DETAILS"))["thinkwise"]["users"]

@router.post("/forgot-password")
async def forgot_password(req: PasswordResetRequest, background_tasks: BackgroundTasks):
    user = await user_col.find_one({ "email": req.email })
    if not user:
        # To avoid user enumeration, respond with 200 anyway
        return { "message": "If that email exists, you’ll get a reset link." }

    # 1) Create one-time JWT with short expiry
    token = create_password_reset_token({ "sub": str(user["_id"]) })

    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    reset_link = f"{frontend_base}/reset-password?token={token}"


    # 2) Email the link
    background_tasks.add_task(
      send_email,
      subject="Password Reset for Thinkwise",
      recipients=[req.email],
      body=f"Click <a href='{reset_link}'>here</a> to reset your password."
    )
    return { "message": "If that email exists, you’ll get a reset link." }

@router.post("/reset-password")
async def reset_password(data: PasswordReset):
    # 1) verify token, extract user_id
    try:
        payload = verify_password_reset_token(data.token)
        uid = payload["sub"]
    except:
        raise HTTPException(400, "Invalid or expired token")

    # 2) update DB
    await user_col.update_one(
      { "_id": ObjectId(uid) },
      { "$set": { "hashed_password": hash_password(data.new_password) } }
    )
    return { "message": "Password has been reset." }
