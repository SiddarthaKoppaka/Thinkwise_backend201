import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URI)

async def check_database():
    # List all databases
    databases = await mongo_client.list_database_names()
    print("Databases on this server:")
    for db in databases:
        print("-", db)

    # Check if a specific database exists
    db_name_to_check = "thinkwise"
    if db_name_to_check in databases:
        print(f"\n✅ Database '{db_name_to_check}' exists.")

        # Access the collection
        db = mongo_client[db_name_to_check]
        collection = db["analysis"]

        print("\n🔎 Top 3 documents in 'analysis' collection:")
        cursor = collection.find().limit(3)
        async for document in cursor:
            print(document)

    else:
        print(f"\n❌ Database '{db_name_to_check}' does not exist.")

# Run the async function
asyncio.run(check_database())
