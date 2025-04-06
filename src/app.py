import os
import io
import json
import datetime
import traceback
import pandas as pd
from fastapi import Query
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from src.agent.agent import outer_workflow  # Original graph-based workflow
from src.agent.agent_lcel import outer_chain  # LCEL-based chain

# -----------------------
# App Initialization
# -----------------------
app = FastAPI(title="Thinkwise Idea Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Database Setup
# -----------------------
MONGO_URI = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["thinkwise"]
collection = db.analysis

# -----------------------
# Helper Functions
# -----------------------

async def upsert_analysis(idea):
    idea["last_updated"] = datetime.datetime.utcnow()
    await collection.update_one({"idea_id": idea["idea_id"]}, {"$set": idea}, upsert=True)
import io
import json
import datetime
import pandas as pd

def parse_ideas_file(filename, content):
    def safe_str(val):
        # Check if the value is missing (NaN) and return an empty string if so,
        # otherwise return the string version of the value.
        if pd.isna(val):
            return ""
        return str(val)

    ideas = {}
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
        print("🧾 CSV Headers:", df.columns.tolist())
        print("🧾 First 5 Rows:")
        print(df.head())

        # Normalize column names to lowercase
        df.columns = [col.strip().lower() for col in df.columns]

        for i, row in df.iterrows():
            # Always generate our own idea ID (ignoring any idea_id present in the CSV)
            idea_id = str(i + 1)
            ideas[idea_id] = {
                "title": safe_str(row.get("idea title", row.get("title", ""))),
                "description": safe_str(row.get("description", "")),
                "author": safe_str(row.get("name", row.get("author", ""))),
                "category": safe_str(row.get("domain", row.get("category", "Uncategorized"))),
                "timestamp": safe_str(row.get("timestamp", datetime.datetime.utcnow())),
            }
    elif filename.endswith(".json"):
        raw = json.loads(content.decode())
        for i, idea in enumerate(raw):
            # Always generate our own idea ID (ignoring any idea_id present in the JSON)
            idea_id = str(i + 1)
            ideas[idea_id] = {
                "title": safe_str(idea.get("title", "")),
                "description": safe_str(idea.get("description", "")),
                "author": safe_str(idea.get("author", "")),
                "category": safe_str(idea.get("category", "Uncategorized")),
                "timestamp": safe_str(idea.get("timestamp", datetime.datetime.utcnow())),
            }
    else:
        raise ValueError("Unsupported file format")
    return ideas
# -----------------------
# Existing Route (Graph-based)
# -----------------------
@app.post("/analyze/csv")
async def analyze_csv(file: UploadFile = File(...)):
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
                "filename": file.filename,  # 📎 Track the file name
            }
            await upsert_analysis(doc)

        # ✅ Return success only, no ideas in response
        return JSONResponse(content={"status": "ok", "filename": file.filename})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# -----------------------
# New Route (LCEL-based)
# -----------------------
@app.post("/analyze/csv/lcel")
async def analyze_csv_lcel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        ideas = parse_ideas_file(file.filename, contents)
        print("📥 Parsed Ideas:", ideas)
        if not ideas:
            raise HTTPException(status_code=422, detail="No valid ideas found in uploaded file.")

        initial_state = {
            "ideas": ideas,
            "weights": {"roi": 0.6, "eie": 0.4}
        }

        final_state = outer_chain.invoke(initial_state)
        processed = final_state.get("processed_ideas", {})

        for idea_id, analysis in processed.items():
            # Calculate a simple score based on ROI/EIE ratio
            roi_score = analysis.get("roi", {}).get("score", 0.0)
            eie_score = analysis.get("eie", {}).get("score", 1.0)
            score = roi_score / eie_score if eie_score != 0 else 0.0

            doc = {
                "idea_id": idea_id,
                "title": ideas[idea_id].get("title", ""),
                "author": ideas[idea_id].get("author", ""),
                "category": ideas[idea_id].get("category", "Uncategorized"),
                "description": ideas[idea_id].get("description", ""),
                "timestamp": ideas[idea_id].get("timestamp", datetime.datetime.utcnow().isoformat()),
                "score": score,
                "roi": roi_score,  # Use numeric score directly
                "effort": eie_score,  # Use numeric score directly
                "analysis": analysis
            }
            await upsert_analysis(doc)

        top_ideas = sorted([
            {
                "idea_id": idea_id,
                "title": ideas[idea_id].get("title", ""),
                "author": ideas[idea_id].get("author", ""),
                "description": ideas[idea_id].get("description", ""),
                "category": ideas[idea_id].get("category", "Uncategorized"),
                "score": analysis.get("roi", {}).get("score", 0.0) / analysis.get("eie", {}).get("score", 1.0) if analysis.get("eie", {}).get("score", 1.0) != 0 else 0.0,
                "roi": analysis.get("roi", {}).get("score", "Unknown"),
                "effort": analysis.get("eie", {}).get("score", "Unknown")
            }
            for idea_id, analysis in processed.items()
        ], key=lambda x: x["score"], reverse=True)[:3]

        print("📤 Top Ideas (LCEL):", top_ideas)
        return JSONResponse(content={"top_ideas": top_ideas})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# -----------------------
# Existing Route (Get All Ideas)
# -----------------------
def convert_bson_to_json_safe(doc):
    doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc



def convert_document(doc):
    doc["_id"] = str(doc["_id"])
    for key, value in doc.items():
        if isinstance(value, datetime.datetime):  # Correct type check
            doc[key] = value.isoformat()
    return doc


@app.get("/ideas")
async def get_all_ideas():
    ideas = []
    cursor = collection.find()
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"all_ideas": ideas}

@app.get("/ideas/overall_top")
async def get_top_ideas():
    ideas = []
    cursor = collection.find().sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@app.get("/ideas/top")
async def get_top_ideas(filename: str = Query(..., description="The filename to filter ideas from")):
    ideas = []
    cursor = collection.find({"filename": filename}).sort("score", -1).limit(3)
    async for idea in cursor:
        ideas.append(convert_document(idea))
    return {"top_3_ideas": ideas}

@app.get("/data")
async def get_all_ideas():
    try:
        cursor = collection.find({})
        raw_docs = await cursor.to_list(length=1000)
        cleaned_docs = [convert_bson_to_json_safe(doc) for doc in raw_docs]
        return cleaned_docs
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    
    
from fastapi import APIRouter
from collections import defaultdict
from datetime import datetime
from dateutil import parser

@app.get("/analytics")
async def get_analytics():
    try:
        cursor = collection.find({})
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

            # Count category, ROI, Effort
            category_count[category] += 1
            roi_distribution[roi] += 1
            effort_distribution[effort] += 1
            effort_vs_roi[f"{effort}-{roi}"] += 1

            # Score buckets
            if 60 <= score < 70:
                score_buckets["60-69"] += 1
            elif 70 <= score < 80:
                score_buckets["70-79"] += 1
            elif 80 <= score < 90:
                score_buckets["80-89"] += 1
            elif score >= 90:
                score_buckets["90-100"] += 1

            # Category-wise scores
            category_scores[category].append(score)

            # Parse timestamp
            last_updated = idea.get("last_updated")
            try:
                dt = parser.parse(last_updated) if isinstance(last_updated, str) else last_updated
                key = dt.strftime("%Y-%m")
                ideas_over_time[key] += 1
            except:
                continue

        # Prepare final JSON
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
