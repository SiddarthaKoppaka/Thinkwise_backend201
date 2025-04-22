import traceback
import datetime
from collections import defaultdict
from dateutil import parser
from fastapi import APIRouter, Depends, HTTPException, Query
from src.auth.dependencies import get_current_user
from src.core.db import collection
from src.services.idea_service import convert_document

router = APIRouter(prefix="/ideas", tags=["Idea Data & Analytics"])

@router.get("/")
async def get_all_ideas(user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"user_id": user_id})
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"all_ideas": ideas}

@router.get("/overall_top")
async def get_top_ideas(user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"user_id": user_id}).sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@router.get("/top")
async def get_top_ideas_by_file(filename: str = Query(...), user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"filename": filename, "user_id": user_id}).sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@router.get("/data")
async def get_all_data(user_id: str = Depends(get_current_user)):
    try:
        cursor = collection.find({"user_id": user_id})
        raw_docs = await cursor.to_list(length=1000)
        cleaned_docs = [convert_document(doc) for doc in raw_docs]
        return cleaned_docs
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics")
async def get_analytics(user_id: str = Depends(get_current_user)):
    try:
        cursor = collection.find({"user_id": user_id})
        docs = await cursor.to_list(length=1000)

        category_count = defaultdict(int)
        roi_distribution = defaultdict(int)
        effort_distribution = defaultdict(int)
        effort_vs_roi = defaultdict(int)
        score_buckets = {"60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
        category_scores = defaultdict(list)
        ideas_over_time = defaultdict(int)

        for idea in docs:
            category = idea.get("category", "Uncategorized")
            roi = idea.get("roi", "Unknown")
            effort = idea.get("effort", "Unknown")
            score = float(idea.get("score", 0))

            category_count[category] += 1
            roi_distribution[roi] += 1
            effort_distribution[effort] += 1
            effort_vs_roi[f"{effort}-{roi}"] += 1

            if 60 <= score < 70:
                score_buckets["60-69"] += 1
            elif 70 <= score < 80:
                score_buckets["70-79"] += 1
            elif 80 <= score < 90:
                score_buckets["80-89"] += 1
            elif score >= 90:
                score_buckets["90-100"] += 1

            category_scores[category].append(score)

            last_updated = idea.get("last_updated")
            try:
                dt = parser.parse(last_updated) if isinstance(last_updated, str) else last_updated
                key = dt.strftime("%Y-%m")
                ideas_over_time[key] += 1
            except:
                continue

        return {
            "categoryCount": dict(category_count),
            "roiDistribution": dict(roi_distribution),
            "effortDistribution": dict(effort_distribution),
            "effortVsRoi": dict(effort_vs_roi),
            "scoreBuckets": dict(score_buckets),
            "categoryScores": dict(category_scores),
            "ideasOverTime": dict(sorted(ideas_over_time.items()))
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
