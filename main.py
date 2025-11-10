import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Session, ActivityEvent, User

app = FastAPI(title="FocusAI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FocusAI backend running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# ---------- API Models for requests ----------
class StartSessionRequest(BaseModel):
    user_id: str
    goal: str
    duration_minutes: int
    categories: List[str] = []
    voice: Optional[str] = "Cluely"

class UpdateActivityRequest(BaseModel):
    session_id: str
    user_id: str
    app: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    idle: bool = False

class EndSessionRequest(BaseModel):
    session_id: str

# ---------- Simple relevance heuristic ----------
BLOCKLIST_KEYWORDS = {
    "social": ["twitter", "x.com", "facebook", "instagram", "tiktok", "reddit"],
    "nsfw": ["porn", "nsfw", "xxx"],
    "games": ["steam", "epicgames", "roblox", "league of legends", "valorant"],
}

def classify_relevance(goal: str, title: Optional[str], url: Optional[str], categories: List[str]) -> tuple[str, str]:
    text = " ".join([goal.lower(), (title or "").lower(), (url or "").lower()])
    # If explicit blocklisted keyword present for enabled categories -> irrelevant
    for cat in categories:
        for kw in BLOCKLIST_KEYWORDS.get(cat, []):
            if kw in text:
                return "irrelevant", f"Matched blocked keyword '{kw}' in category '{cat}'"
    # If goal keyword present in title/url -> relevant
    goal_words = [w for w in goal.lower().split() if len(w) > 3]
    if any(w in text for w in goal_words):
        return "relevant", "Goal keywords found in current context"
    # Default to relevant unless clearly off-topic
    return "relevant", "No blocklisted signals detected"

# ---------- Endpoints ----------
@app.post("/api/user/register")
def register_user(user: User):
    user_id = create_document("user", user)
    return {"user_id": user_id}

@app.post("/api/session/start")
def start_session(payload: StartSessionRequest):
    session = Session(
        user_id=payload.user_id,
        goal=payload.goal,
        duration_minutes=payload.duration_minutes,
        categories=payload.categories,
        voice=payload.voice or "Cluely",
        started_at=datetime.now(timezone.utc),
        total_focus_seconds=0,
        total_idle_seconds=0,
        distractions_blocked=0,
        status="active",
    )
    session_id = create_document("session", session)
    return {"session_id": session_id, "status": session.status}

@app.post("/api/session/activity")
def update_activity(payload: UpdateActivityRequest):
    # Fetch session
    from bson import ObjectId
    sdocs = list(db["session"].find({"_id": ObjectId(payload.session_id)}))
    if not sdocs:
        raise HTTPException(status_code=404, detail="Session not found")
    sdoc = sdocs[0]

    decision, reason = classify_relevance(sdoc["goal"], payload.title, payload.url, sdoc.get("categories", []))

    event = ActivityEvent(
        session_id=payload.session_id,
        user_id=payload.user_id,
        timestamp=datetime.now(timezone.utc),
        app=payload.app,
        url=payload.url,
        title=payload.title,
        idle=payload.idle,
        decision=decision,
        reason=reason,
    )
    create_document("activityevent", event)

    # Update session counters
    inc = {"distractions_blocked": 1} if decision == "irrelevant" else {"total_focus_seconds": 30}
    db["session"].update_one({"_id": ObjectId(payload.session_id)}, {"$inc": inc, "$set": {"updated_at": datetime.now(timezone.utc)}})

    return {"decision": decision, "reason": reason}

@app.post("/api/session/end")
def end_session(payload: EndSessionRequest):
    from bson import ObjectId
    res = db["session"].update_one(
        {"_id": ObjectId(payload.session_id)},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ended"}

@app.get("/api/session/{user_id}/summary")
def session_summary(user_id: str):
    sessions = get_documents("session", {"user_id": user_id}, limit=50)
    # Basic aggregation in Python for prototype
    total_focus = sum(int(s.get("total_focus_seconds", 0)) for s in sessions)
    total_idle = sum(int(s.get("total_idle_seconds", 0)) for s in sessions)
    distractions = sum(int(s.get("distractions_blocked", 0)) for s in sessions)

    return {
        "sessions": len(sessions),
        "total_focus_seconds": total_focus,
        "total_idle_seconds": total_idle,
        "distractions_blocked": distractions,
        "streak_days": min(len(sessions), 7),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
