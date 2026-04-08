import uuid
import io
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from bootstrap import configure_runtime

configure_runtime()

from models import SearchCriteria
from orchestrator import LeadOrchestrator
import db

app = FastAPI()

# In-memory store for the current server session (fast access during active pipeline).
# The DB is the persistent source of truth across restarts.
session_storage: dict[str, bytes] = {}
session_status:  dict[str, dict]  = {}
recent_sessions: list[str]        = []


class StatusTrackingWebSocket:
    def __init__(self, websocket: WebSocket, session_id: str):
        self._ws         = websocket
        self._session_id = session_id

    async def send_json(self, data):
        if isinstance(data, dict):
            session_status[self._session_id] = {
                **session_status.get(self._session_id, {}),
                **{k: v for k, v in data.items()
                   if k in ("status", "step", "label", "code", "message", "details")},
                "session_id": self._session_id,
            }
        await self._ws.send_json(data)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status/{session_id}")
async def get_status(session_id: str):
    status = session_status.get(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return status


@app.get("/history")
async def get_history():
    """Return all previously completed lead generation sessions."""
    sessions = await db.list_sessions()
    return {"sessions": sessions}


@app.websocket("/ws/generate")
async def generate_leads(websocket: WebSocket):
    await websocket.accept()
    try:
        data     = await websocket.receive_json()
        criteria = SearchCriteria(**data)

        session_id = str(uuid.uuid4())
        session_status[session_id] = {"status": "running", "step": 0, "session_id": session_id}
        recent_sessions.append(session_id)

        # Persist the session immediately so history shows it even before completion.
        await db.save_session(
            session_id, criteria.model_dump(), status="running"
        )

        await websocket.send_json({"status": "started", "session_id": session_id})

        tracking_ws  = StatusTrackingWebSocket(websocket, session_id)
        orchestrator = LeadOrchestrator(criteria, tracking_ws)
        excel_data   = await orchestrator.run_pipeline()

        if excel_data:
            session_storage[session_id] = excel_data

            success = orchestrator.last_success or {}
            ready_status = {"status": "ready", "session_id": session_id, **success}
            session_status[session_id] = ready_status

            # Persist to DB so history survives restarts.
            await db.save_session(
                session_id,
                criteria.model_dump(),
                status="ready",
                total_leads=success.get("total_leads", 0),
                verified=success.get("verified", 0),
                missing_email=success.get("missing_email", 0),
                preview=success.get("preview", []),
                excel_data=excel_data,
            )

            payload = {"status": "ready", "session_id": session_id,
                       "message": "Leads generated successfully!", **success}
            try:
                await tracking_ws.send_json(payload)
            except Exception:
                pass
        else:
            err = orchestrator.last_error or {
                "status": "error", "code": "PIPELINE_FAILED",
                "message": "Pipeline failed to generate leads.",
            }
            session_status[session_id] = {**err, "session_id": session_id}
            await db.save_session(session_id, criteria.model_dump(), status="error")
            try:
                await tracking_ws.send_json(err)
            except Exception:
                pass

    except ValidationError as e:
        await websocket.send_json(
            {"status": "error", "code": "INVALID_CRITERIA",
             "message": f"Invalid criteria: {str(e)}"}
        )
    except Exception as e:
        await websocket.send_json(
            {"status": "error", "code": "SERVER_ERROR",
             "message": f"Server error: {str(e)}"}
        )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/download/{session_id}")
async def download_excel(session_id: str):
    # Check in-memory first (current session), then fall back to DB (previous sessions).
    data = session_storage.get(session_id) or await db.get_excel(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=leads_{session_id[:8]}.xlsx"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
