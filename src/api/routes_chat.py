import traceback
from fastapi import APIRouter, Query, Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId

from src.auth.dependencies import get_current_user
from src.agent.react_idea_agent import build_react_chat_agent
from src.core.db import collection, MONGO_URI

router = APIRouter(prefix="/chat", tags=["Chat with Idea Agent"])

def safe_float(value, default):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


@router.post("/idea/{id}")
async def chat_with_idea(
    id: str,
    message: str = Query(..., description="User message to the idea agent"),
    current_user: dict = Depends(get_current_user)
):
    # Extract your user’s ID from the JWT 'sub'
    user_id = current_user["sub"]

    # Convert the path param into a BSON ObjectId
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid idea ID format.")

    try:
        # Now fetch by _id and user_id
        idea = await collection.find_one({"_id": obj_id, "user_id": user_id})
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found for this user.")
        idea_id = idea["idea_id"]
        description = idea.get("description", "")
        roi = safe_float(idea.get("roi"), 0.0)
        effort = safe_float(idea.get("effort"), 1.0)

        agent = build_react_chat_agent(
            idea_id=idea_id,
            idea_description=description,
            roi=roi,
            effort=effort,
            user_id=user_id,
            mongo_uri=MONGO_URI
        )

        response = agent.invoke({"input": message})
        return {"idea_id": idea_id, "response": response}

    except HTTPException:
        # re-raise known HTTP errors
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
