from fastapi import APIRouter, HTTPException, BackgroundTasks
from .models import PasswordResetRequest, PasswordReset
from .utils import create_password_reset_token, verify_password_reset_token, hash_password
from .email import send_email
from motor.motor_asyncio import AsyncIOMotorClient
import os
import datetime
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


    # 2) Email the reset link with styled HTML
background_tasks.add_task(
  send_email,
  subject="Reset Your Thinkwise Password",
  recipients=[req.email],
  body=f"""
<html>
  <body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:20px 0;">
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
                  Reset Your Password
                </h1>
              </td>
            </tr>
            <!-- Body -->
            <tr>
              <td style="padding:30px;color:#333333;font-size:16px;line-height:1.5;">
                <p>Hi there,</p>
                <p>
                  We received a request to reset your Thinkwise password.
                  If you made this request, please click the button below.
                </p>
                <p style="text-align:center;margin:30px 0;">
                  <a href="{reset_link}" style="
                    display:inline-block;
                    padding:12px 24px;
                    background-color:#1a73e8;
                    color:#ffffff;
                    text-decoration:none;
                    border-radius:6px;
                    font-weight:bold;
                  ">
                    Reset Password
                  </a>
                </p>
                <p>If you didn’t request a password reset, you can safely ignore this email.</p>
                <p>This link will expire in 15 minutes for your security.</p>
                <p>Best,<br/>The Thinkwise Team</p>
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
