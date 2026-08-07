import os
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime, timezone

from db import db
from auth import get_current_user
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

advisor_router = APIRouter(prefix="/api/advisor")

# Default routing: Claude Sonnet 5 for executive synthesis, Gemini 3.1 Pro for long-context ingestion
MODEL_ROUTES = {
    "executive": ("anthropic", "claude-sonnet-5"),
    "operational": ("anthropic", "claude-sonnet-5"),
    "ingestion": ("gemini", "gemini-3.1-pro-preview"),
}


class AdvisorQuery(BaseModel):
    message: str
    mode: str = "executive"
    session_id: str | None = None


async def _build_context(org_id: str) -> str:
    risks = await db.risks.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    health = await db.health_index.find_one({"org_id": org_id}, {"_id": 0})
    ai_systems = await db.ai_systems.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    incidents = await db.ai_incidents.find({"org_id": org_id}, {"_id": 0}).to_list(50)
    ctx = {
        "enterprise_health": health,
        "risks": [{"ref": r["ref"], "title": r["title"], "residual": r["residual"],
                   "inherent": r["inherent"], "status": r["status"], "owner": r["owner"],
                   "source": r["source"], "confidence": r["confidence"], "data_type": r["data_type"],
                   "business_impact": r.get("business_impact")} for r in risks],
        "ai_systems": [{"ref": a["ref"], "name": a["name"], "status": a["status"],
                        "risk_class": a["risk_class"], "drift": a["drift"]} for a in ai_systems],
        "ai_incidents": [{"ref": i["ref"], "title": i["title"], "severity": i["severity"],
                          "status": i["status"]} for i in incidents],
    }
    return json.dumps(ctx, default=str)


SYSTEM_PROMPT = """You are the Obserra EIOS Evidence-Grounded Advisor for enterprise cyber-risk and AI governance.
RULES:
- Ground EVERY claim in the provided ENTERPRISE CONTEXT. Cite specific refs (e.g. CR-001, AI-002) in square brackets.
- Clearly separate FACT (from connected systems), ESTIMATE (modeled), PREDICTION (forward-looking), and RECOMMENDATION.
- Attach a confidence level (High/Medium/Low) to recommendations and note data freshness when relevant.
- Executive mode: concise, business-impact framed, board-ready. Operational mode: control-level detail, remediation steps.
- Never fabricate data not present in the context. If unknown, say so.
Format with short markdown. Prefix recommendations with 'RECOMMENDATION:'."""


@advisor_router.post("/chat")
async def advisor_chat(body: AdvisorQuery, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    context = await _build_context(org_id)
    provider, model = MODEL_ROUTES.get(body.mode, MODEL_ROUTES["executive"])
    session_id = body.session_id or f"{org_id}-{user['id']}"

    await db.advisor_logs.insert_one({
        "org_id": org_id, "user": user["email"], "mode": body.mode, "model": f"{provider}/{model}",
        "prompt": body.message, "ts": datetime.now(timezone.utc).isoformat(),
    })

    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model(provider, model)

    full_prompt = f"ENTERPRISE CONTEXT (JSON):\n{context}\n\nQUESTION ({body.mode} mode): {body.message}"

    async def event_generator():
        collected = []
        try:
            async for event in chat.stream_message(UserMessage(text=full_prompt)):
                if isinstance(event, TextDelta):
                    collected.append(event.content)
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            yield f"data: {json.dumps({'delta': f'[advisor error: {str(e)}]'})}\n\n"
        await db.advisor_logs.update_one(
            {"org_id": org_id, "user": user["email"], "prompt": body.message},
            {"$set": {"response": "".join(collected)}}, upsert=False)
        yield f"data: {json.dumps({'done': True, 'model': f'{provider}/{model}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@advisor_router.get("/logs")
async def advisor_logs(user: dict = Depends(get_current_user)):
    logs = await db.advisor_logs.find({"org_id": user["org_id"]}, {"_id": 0}).sort("ts", -1).to_list(50)
    return logs
