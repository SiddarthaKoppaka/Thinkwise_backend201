import os
import io
import json
import datetime
import traceback
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
from dateutil import parser
from src.auth.dependencies import get_current_user
from src.auth.routes import router as auth_router
from src.agent.agent import outer_workflow
from src.agent.agent_lcel import outer_chain
from src.utils.parser import parse_ideas_file

app = FastAPI(title="Thinkwise Idea Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")


MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["thinkwise"]
collection = db.analysis

async def upsert_analysis(idea, user_id):
    idea["user_id"] = user_id
    idea["last_updated"] = datetime.datetime.utcnow()
    await collection.update_one(
        {"idea_id": idea["idea_id"], "user_id": user_id},
        {"$set": idea},
        upsert=True
    )

def convert_document(doc):
    doc["_id"] = str(doc["_id"])
    for key, value in doc.items():
        if isinstance(value, datetime.datetime):
            doc[key] = value.isoformat()
    return doc

@app.post("/analyze/csv")
async def analyze_csv(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    try:
        contents = await file.read()
        ideas = parse_ideas_file(file.filename, contents)
        if not ideas:
            raise HTTPException(status_code=422, detail="No valid ideas found in uploaded file.")

        initial_outer_state = {
            "ideas": ideas,
            "processed_ideas": {},
            "feedback": {},
            "weights": {"roi": 0.6, "eie": 0.4},
            "summary": {}
        }

        final_state = outer_workflow.invoke(initial_outer_state, {"recursion_limit": 100})
        processed = final_state.get("processed_ideas", {})

        for idea_id, analysis in processed.items():
            doc = {
                "idea_id": idea_id,
                "title": ideas[idea_id].get("title", ""),
                "author": ideas[idea_id].get("author", ""),
                "category": ideas[idea_id].get("category", "Uncategorized"),
                "description": ideas[idea_id].get("description", ""),
                "timestamp": ideas[idea_id].get("timestamp", datetime.datetime.utcnow().isoformat()),
                "score": analysis.get("score", 0),
                "roi": analysis.get("roi", {}).get("label", "Unknown"),
                "effort": analysis.get("eie", {}).get("label", "Unknown"),
                "analysis": analysis,
                "filename": file.filename
            }
            print(doc)
            await upsert_analysis(doc, user_id)

        return JSONResponse(content={"status": "ok", "filename": file.filename})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# @app.post("/analyze/csv/lcel")
# async def analyze_csv_lcel(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
#     try:
#         contents = await file.read()
#         ideas = parse_ideas_file(file.filename, contents)
#         if not ideas:
#             raise HTTPException(status_code=422, detail="No valid ideas found in uploaded file.")

#         initial_state = {
#             "ideas": ideas,
#             "weights": {"roi": 0.6, "eie": 0.4}
#         }

#         final_state = outer_chain.invoke(initial_state)
#         processed = final_state.get("processed_ideas", {})

#         for idea_id, analysis in processed.items():
#             roi_score = analysis.get("roi", {}).get("score", 0.0)
#             eie_score = analysis.get("eie", {}).get("score", 1.0)
#             score = roi_score / eie_score if eie_score else 0.0

#             doc = {
#                     "idea_id": idea_id,
#                     "title": analysis.get("title") or analysis.get("final_summary", {}).get("title", ""),
#                     "author": analysis.get("author") or analysis.get("final_summary", {}).get("author", ""),
#                     "category": analysis.get("category") or analysis.get("final_summary", {}).get("category", "Uncategorized"),
#                     "description": analysis.get("description") or analysis.get("final_summary", {}).get("description", ""),
#                     "timestamp": analysis.get("timestamp", datetime.datetime.utcnow().isoformat()),
#                     "score": score,
#                     "roi": roi_score,
#                     "effort": eie_score,
#                     "analysis": analysis,
#                     "filename": file.filename
#                 }

#             await upsert_analysis(doc, user_id)

#         top_ideas = sorted([
#             {
#                 "idea_id": idea_id,
#                 "title": ideas[idea_id].get("title", ""),
#                 "author": ideas[idea_id].get("author", ""),
#                 "description": ideas[idea_id].get("description", ""),
#                 "category": ideas[idea_id].get("category", "Uncategorized"),
#                 "score": analysis.get("roi", {}).get("score", 0.0) / analysis.get("eie", {}).get("score", 1.0) if analysis.get("eie", {}).get("score", 1.0) != 0 else 0.0,
#                 "roi": analysis.get("roi", {}).get("score", "Unknown"),
#                 "effort": analysis.get("eie", {}).get("score", "Unknown")
#             }
#             for idea_id, analysis in processed.items()
#         ], key=lambda x: x["score"], reverse=True)[:3]

#         return JSONResponse(content={"top_ideas": top_ideas})

#     except Exception as e:
#         traceback.print_exc()
#         return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/ideas")
async def get_all_ideas(user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"user_id": user_id})
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"all_ideas": ideas}

@app.get("/ideas/overall_top")
async def get_top_ideas(user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"user_id": user_id}).sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@app.get("/ideas/top")
async def get_top_ideas(filename: str = Query(...), user_id: str = Depends(get_current_user)):
    ideas = []
    cursor = collection.find({"filename": filename, "user_id": user_id}).sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@app.get("/data")
async def get_all_data(user_id: str = Depends(get_current_user)):
    try:
        cursor = collection.find({"user_id": user_id})
        raw_docs = await cursor.to_list(length=1000)
        cleaned_docs = [convert_document(doc) for doc in raw_docs]
        return cleaned_docs
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
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
