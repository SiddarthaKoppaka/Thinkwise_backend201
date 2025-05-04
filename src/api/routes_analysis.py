import datetime
import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from src.core.db import collection
from src.auth.dependencies import get_current_user
from src.agent.agent import outer_workflow
from src.utils.parser import parse_ideas_file
from src.auth.models import SingleIdea
from src.services.idea_service import upsert_analysis, convert_document

router = APIRouter(prefix="/analyze", tags=["Analysis"])

@router.post("/csv")
async def analyze_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    roi_weight: float = Query(0.6, ge=0, le=1, description="Weight for ROI (0 to 1)"),
    eie_weight: float = Query(0.4, ge=0, le=1, description="Weight for EIE (0 to 1)")
):
    user_sub = current_user["sub"]
    try:
        # Validate that weights sum to ~1.0
        if not (0.99 <= roi_weight + eie_weight <= 1.01):
            raise HTTPException(status_code=400, detail="ROI and EIE weights must sum to 1.0")

        contents = await file.read()
        ideas = parse_ideas_file(file.filename, contents)
        if not ideas:
            raise HTTPException(status_code=422, detail="No valid ideas found in uploaded file.")

        initial_outer_state = {
            "ideas": ideas,
            "processed_ideas": {},
            "feedback": {},
            "weights": {"roi": roi_weight, "eie": eie_weight},
            "summary": {}
        }

        final_state = outer_workflow.invoke(initial_outer_state, {"recursion_limit": 100})
        processed = final_state.get("processed_ideas", {})

        for idea_id, analysis in processed.items():
            roi_score = analysis.get("roi", {}).get("score", 0.0)
            eie_score = analysis.get("eie", {}).get("score", 0.0)
            combined_score = roi_weight * roi_score + eie_weight * eie_score

            doc = {
                "idea_id": idea_id,
                "title": ideas[idea_id].get("title", ""),
                "author": ideas[idea_id].get("author", ""),
                "category": ideas[idea_id].get("category", "Uncategorized"),
                "description": ideas[idea_id].get("description", ""),
                "timestamp": ideas[idea_id].get("timestamp", datetime.datetime.utcnow().isoformat()),
                "score": combined_score,
                "roi": roi_score,
                "effort": eie_score,
                "analysis": analysis,
                "filename": file.filename
                }
            await upsert_analysis(collection, doc, user_sub)

        return JSONResponse(content={"status": "ok", "filename": file.filename})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/single")
async def analyze_single(
    idea: SingleIdea = Body(...),
    current_user: dict = Depends(get_current_user),
    roi_weight: float = Query(0.6, ge=0, le=1, description="Weight for ROI (0 to 1)"),
    eie_weight: float = Query(0.4, ge=0, le=1, description="Weight for EIE (0 to 1)")
):
    user_sub = current_user["sub"]
    # validate weights
    if not (0.99 <= roi_weight + eie_weight <= 1.01):
        raise HTTPException(status_code=400, detail="ROI and EIE weights must sum to 1.0")

    # assign a random ID and timestamp
    idea_id = str(uuid.uuid4())
    ts = idea.timestamp or datetime.datetime.utcnow().isoformat()

    # wrap it into the same 'ideas' dict your agent expects
    initial_outer_state = {
        "ideas": {
            idea_id: {
                "title":       idea.title,
                "author":      idea.author,
                "category":    idea.category,
                "description": idea.description,
                "timestamp":   ts
            }
        },
        "processed_ideas": {},
        "feedback": {},
        "weights": {"roi": roi_weight, "eie": eie_weight},
        "summary": {}
    }

    try:
        # invoke the same outer_workflow
        final_state = outer_workflow.invoke(initial_outer_state, {"recursion_limit": 100})
        processed = final_state.get("processed_ideas", {})
        analysis = processed.get(idea_id)
        if analysis is None:
            raise HTTPException(status_code=500, detail="Agent returned no analysis")

        # compute combined score
        roi_score = analysis.get("roi", {}).get("score", 0.0)
        eie_score = analysis.get("eie", {}).get("score", 0.0)
        combined = roi_weight * roi_score + eie_weight * eie_score

        # upsert into your DB
        doc = {
            "idea_id":    idea_id,
            "title":      idea.title,
            "author":     idea.author,
            "category":   idea.category,
            "description":idea.description,
            "timestamp":  ts,
            "score":      combined,
            "roi":        roi_score,
            "effort":     eie_score,
            "analysis":   analysis,
            "filename":   "Single"
        }
        await upsert_analysis(collection, doc, user_sub)

        return {"status": "ok", "idea_id": idea_id, "analysis": analysis}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))