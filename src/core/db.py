# src/core/db.py
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_DETAILS")
print(MONGO_URI)
if not MONGO_URI:
    raise RuntimeError("❌ MONGO_DETAILS not found in environment variables.")

mongo_client = AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,  # 5 sec to find the server
    connectTimeoutMS=5000,          # 5 sec to connect
)
db = mongo_client["thinkwise"]
collection = db.analysis
