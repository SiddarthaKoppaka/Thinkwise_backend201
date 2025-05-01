import traceback
import datetime
from collections import defaultdict
from dateutil import parser
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient

from src.auth.dependencies import get_current_user
from src.core.db import collection, MONGO_URI
from src.services.idea_service import convert_document

router = APIRouter(prefix="/ideas", tags=["Idea Data & Analytics"])

def safe_float(value):
        try:
            return float(value)
        except ValueError:
            return None

@router.get("/")
async def get_all_ideas(current_user: dict = Depends(get_current_user)):
    user_sub = current_user["sub"]
    ideas = []
    cursor = collection.find({"user_id": user_sub})
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"all_ideas": ideas}

@router.get("/overall_top")
async def get_top_ideas(current_user: dict = Depends(get_current_user)):
    user_sub = current_user["sub"]
    cursor = collection.find({"user_id": user_sub}).sort("score", -1).limit(3)
    ideas = []
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@router.get("/top")
async def get_top_ideas_by_file(
    filename: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    user_sub = current_user["sub"]
    cursor = collection.find({
        "filename": filename,
        "user_id": user_sub
    }).sort("score", -1).limit(3)
    ideas = []
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@router.get("/data")
async def get_all_data(
    current_user: dict = Depends(get_current_user)
):
    """
    Return every idea document for the logged-in user.
    """
    user_sub = current_user["sub"]
    try:
        cursor = collection.find({"user_id": user_sub})
        raw_docs = await cursor.to_list(length=1000)
        cleaned = [convert_document(doc) for doc in raw_docs]
        return {"data": cleaned}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics")
async def get_analytics(current_user: dict = Depends(get_current_user)):
    """
    Compute summary metrics (counts, distributions, time series)
    for the user's ideas, with ROI/Effort/Score on a 0–100 scale.
    """
    user_sub = current_user["sub"]

    try:
        docs = await collection.find({"user_id": user_sub}).to_list(length=1000)

        # Counters & buckets
        category_count      = defaultdict(int)
        roi_distribution    = defaultdict(int)
        effort_distribution = defaultdict(int)
        effort_vs_roi       = defaultdict(int)
        # include 0–59 bucket now
        score_buckets       = {
            "0-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0
        }
        category_scores     = defaultdict(list)
        ideas_over_time     = defaultdict(int)

        for idea in docs:
            # 1) Category count
            cat = idea.get("category", "Uncategorized")
            category_count[cat] += 1

            # 2) Scale ROI & Effort to percent
            raw_roi = safe_float(idea.get("roi"))
            roi_pct = int(round(raw_roi * 100))
            roi_distribution[roi_pct] += 1

            raw_eff = safe_float(idea.get("effort"))
            eff_pct = int(round(raw_eff * 100))
            effort_distribution[eff_pct] += 1

            # 3) Effort vs ROI (percent key)
            effort_vs_roi[f"{eff_pct}-{roi_pct}"] += 1

            # 4) Overall score percent (using stored `score` field)
            raw_score = safe_float(idea.get("score"))
            score_pct = int(round(raw_score * 100))
            category_scores[cat].append(score_pct)

            # bucket the overall score
            if score_pct < 60:
                score_buckets["0-59"] += 1
            elif score_pct < 70:
                score_buckets["60-69"] += 1
            elif score_pct < 80:
                score_buckets["70-79"] += 1
            elif score_pct < 90:
                score_buckets["80-89"] += 1
            else:
                score_buckets["90-100"] += 1

            # 5) Time series by last_updated month
            last_up = idea.get("last_updated")
            try:
                dt = parser.parse(last_up) if isinstance(last_up, str) else last_up
                key = dt.strftime("%Y-%m")
                ideas_over_time[key] += 1
            except:
                continue

        return {
            "categoryCount":      dict(category_count),
            "roiDistribution":    dict(roi_distribution),
            "effortDistribution": dict(effort_distribution),
            "effortVsRoi":        dict(effort_vs_roi),
            "scoreBuckets":       score_buckets,
            "categoryScores":     {k: v for k, v in category_scores.items()},
            "ideasOverTime":      dict(sorted(ideas_over_time.items()))
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to compute analytics")

@router.get("/{id}")
async def get_idea_by_id(
    id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Fetch a single idea by its MongoDB _id.
    """
    user_sub = current_user["sub"]

    try:
        oid = ObjectId(id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid idea ID format")

    doc = await collection.find_one({"_id": oid, "user_id": user_sub})
    if not doc:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea = convert_document(doc)
    # include chat history if present
    idea["chat_history"] = doc.get("chat_history", [])
    return {"idea": idea}

@router.get("/{id}/history")
async def get_chat_history(
    id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Return the full chat_history for a given idea + user, in chronological order.
    """
    user_id = current_user["sub"]
    session_id = f"{user_id}_{id}"

    client = AsyncIOMotorClient(MONGO_URI)
    db = client["thinkwise_chat"]
    memcol = db["memory"]

    cursor = memcol.find({"session_id": session_id}).sort("timestamp", 1)
    history = []
    async for doc in cursor:
        history.append({
            "from": doc.get("type"),
            "text": doc.get("data", {}).get("text", ""),
            "timestamp": doc.get("timestamp").isoformat() if doc.get("timestamp") else None
        })

    return {"chat_history": history}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_idea(
    id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a single idea by its MongoDB _id."""
    user_sub = current_user["sub"]
    try:
        oid = ObjectId(id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid idea ID format")

    result = await collection.delete_one({"_id": oid, "user_id": user_sub})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Idea not found or not yours")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_ideas(
    current_user: dict = Depends(get_current_user)
):
    """Delete *all* ideas belonging to the current user."""
    user_sub = current_user["sub"]
    await collection.delete_many({"user_id": user_sub})
    return Response(status_code=status.HTTP_204_NO_CONTENT)