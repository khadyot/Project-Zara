from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
import uvicorn
from zara.models import Prospect, SourceResult, SignalCard
from zara.orchestrator import run_pipeline

app = FastAPI()

class WebhookPayload(BaseModel):
    prospect: Prospect
    source_payloads: Dict[str, Any]

@app.post("/pipeline/run")
async def pipeline_run(payload: WebhookPayload):
    # In a full implementation, we'd map the raw Apify JSON in `source_payloads`
    # to SourceResult and SignalCards here.
    # For now, we'll just run the pipeline with lean profile or return dummy.
    # As ranking and drafting are built in Slice 2, this will return the final artifact.
    
    # Just a placeholder for the webhook contract
    return {"status": "ok", "message": "Pipeline triggered"}

if __name__ == "__main__":
    uvicorn.run("zara.server:app", host="0.0.0.0", port=8000, reload=True)
