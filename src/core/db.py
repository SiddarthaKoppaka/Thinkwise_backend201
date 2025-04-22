import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()  # Load variables from .env

MONGO_URI = os.getenv("MONGO_DETAILS")

if not MONGO_URI:
    raise RuntimeError("❌ MONGO_DETAILS not found in environment variables.")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["thinkwise"]
collection = db.analysis
