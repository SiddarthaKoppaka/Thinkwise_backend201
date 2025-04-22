# src/services/idea_service.py

import datetime

def convert_document(doc):
    doc["_id"] = str(doc["_id"])
    for key, value in doc.items():
        if isinstance(value, datetime.datetime):
            doc[key] = value.isoformat()
    return doc

async def upsert_analysis(collection, idea, user_id):
    idea["user_id"] = user_id
    idea["last_updated"] = datetime.datetime.utcnow()
    await collection.update_one(
        {"idea_id": idea["idea_id"], "user_id": user_id},
        {"$set": idea},
        upsert=True
    )
