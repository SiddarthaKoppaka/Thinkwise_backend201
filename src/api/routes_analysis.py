import datetime
import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from src.core.db import collection
from src.auth.dependencies import get_current_user
from src.agent.agent import outer_workflow
from src.utils.parser import parse_ideas_file
from src.services.idea_service import upsert_analysis, convert_document

router = APIRouter(prefix="/analyze", tags=["Analysis"])

@router.post("/csv")
async def analyze_csv(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    roi_weight: float = Query(0.6, ge=0, le=1, description="Weight for ROI (0 to 1)"),
    eie_weight: float = Query(0.4, ge=0, le=1, description="Weight for EIE (0 to 1)")
):
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
            await upsert_analysis(collection, doc, user_id)

        return JSONResponse(content={"status": "ok", "filename": file.filename})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
