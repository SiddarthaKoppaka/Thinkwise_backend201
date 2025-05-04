from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from .models import UserRegister, UserLogin, Token, UserProfile
from .utils import hash_password, verify_password, create_token
from motor.motor_asyncio import AsyncIOMotorClient
import os
from src.auth.dependencies import get_current_user
from src.core.config import settings
from .email import send_email
import datetime

router = APIRouter()

MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
user_collection = client["thinkwise"]["users"]

@router.post("/register", response_model=Token)
async def register(
    user: UserRegister,
    background_tasks: BackgroundTasks
):
    # 1) check duplicate
    if await user_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2) create user
    result = await user_collection.insert_one({
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "hashed_password": hash_password(user.password),
    })
    user_id = str(result.inserted_id)

    # 3) send welcome email in background
    background_tasks.add_task(
    send_email,
    subject="Welcome to Thinkwise – Let’s get started!",
    recipients=[user.email],
    body=f"""
<html>
  <body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:20px 0;">
          <!-- Logo -->
          <img
            src="https://your-cdn.com/assets/thinkwise-logo.png"
            alt="Thinkwise Logo"
            width="120"
            style="display:block;"
          />
        </td>
      </tr>
      <tr>
        <td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
            <!-- Header -->
            <tr>
              <td style="background-color:#1a73e8;padding:30px;text-align:center;">
                <h1 style="color:#ffffff;font-size:24px;margin:0;">
                  Welcome to Thinkwise, {user.first_name}!
                </h1>
              </td>
            </tr>
            <!-- Body -->
            <tr>
              <td style="padding:30px;color:#333333;font-size:16px;line-height:1.5;">
                <p>Hi {user.first_name},</p>
                <p>
                  We’re thrilled you’ve joined Thinkwise! Our platform
                  helps you turn your best ideas into actionable insights.
                </p>
                <p>Here’s how to get started:</p>
                <ul style="margin:0 0 20px 20px;">
                  <li>🔹 Upload a CSV of ideas or submit a single idea.</li>
                  <li>🔹 Set your ROI &amp; Effort weights to match your goals.</li>
                  <li>🔹 Explore your top suggestions and iterate.</li>
                </ul>
                <p>
                  Got questions? Reply to this email or visit our
                  <a href="https://thinkwise.com/help" style="color:#1a73e8;">
                    Help Center
                  </a>.
                </p>
                <p>Cheers,<br/>The Thinkwise Team</p>
              </td>
            </tr>
            <!-- Footer -->
            <tr>
              <td style="background:#f4f4f4;padding:20px;text-align:center;font-size:12px;color:#777777;">
                © {datetime.datetime.utcnow().year} Thinkwise. All rights reserved.<br/>
                1234 Innovation Drive, Suite 100, City, State ZIP
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
)

    # 4) generate token exactly like in /login
    token = create_token({
        "sub": user_id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
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
