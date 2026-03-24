import uuid
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import io

from bootstrap import configure_runtime

configure_runtime()

from models import SearchCriteria
from orchestrator import LeadOrchestrator

app = FastAPI()

# Store CSV strings in memory dict keyed by session_id
session_storage = {}
# Store session status for UI/debugging
session_status = {}

class StatusTrackingWebSocket:
    def __init__(self, websocket: WebSocket, session_id: str):
        self._ws = websocket
        self._session_id = session_id

    async def send_json(self, data):
        # Keep a server-side status record for polling, even if the WS drops.
        if isinstance(data, dict):
            session_status[self._session_id] = {
                **session_status.get(self._session_id, {}),
                **{k: v for k, v in data.items() if k in ("status", "step", "label", "code", "message", "details")},
                "session_id": self._session_id,
            }
        await self._ws.send_json(data)

app.add_middleware(
    CORSMiddleware,
    # Dev-friendly CORS for WSL2 + Windows browsers.
    # We don't rely on cookies here, so allow any origin and disable credentials.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/status/{session_id}")
def get_status(session_id: str):
    status = session_status.get(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return status

@app.websocket("/ws/generate")
async def generate_leads(websocket: WebSocket):
    await websocket.accept()
    try:
        # Receive JSON -> parse as SearchCriteria
        data = await websocket.receive_json()
        criteria = SearchCriteria(**data)
        
        # Generate session_id (uuid4)
        session_id = str(uuid.uuid4())
        session_status[session_id] = {"status": "running", "step": 0, "session_id": session_id}

        # Send session_id immediately so the UI can reference it even if the socket drops.
        await websocket.send_json({"status": "started", "session_id": session_id})
        
        # Call run_pipeline(criteria, websocket)
        tracking_ws = StatusTrackingWebSocket(websocket, session_id)
        orchestrator = LeadOrchestrator(criteria, tracking_ws)
        csv_data = await orchestrator.run_pipeline()
        
        if csv_data:
            # Store CSV string in memory
            session_storage[session_id] = csv_data
            ready_status = {"status": "ready", "session_id": session_id}
            if orchestrator.last_success:
                ready_status.update(orchestrator.last_success)
            session_status[session_id] = ready_status
            
            # Send: {status:"ready", session_id, message}
            payload = {
                "status": "ready",
                "session_id": session_id,
                "message": "Leads generated successfully!"
            }
            if orchestrator.last_success:
                payload.update(orchestrator.last_success)
            try:
                await tracking_ws.send_json(payload)
            except Exception:
                pass  # Client disconnected before we could send the final ready message
        else:
            # Prefer the detailed reason sent by the orchestrator (step=0).
            if orchestrator.last_error:
                session_status[session_id] = {**orchestrator.last_error, "session_id": session_id}
                try:
                    await tracking_ws.send_json(orchestrator.last_error)
                except Exception:
                    pass
            else:
                session_status[session_id] = {"status": "error", "code": "PIPELINE_FAILED", "message": "Pipeline failed to generate leads.", "session_id": session_id}
                try:
                    await tracking_ws.send_json({
                        "status": "error",
                        "code": "PIPELINE_FAILED",
                        "message": "Pipeline failed to generate leads."
                    })
                except Exception:
                    pass
            
    except ValidationError as e:
        await websocket.send_json(
            {"status": "error", "code": "INVALID_CRITERIA", "message": f"Invalid criteria: {str(e)}"}
        )
    except Exception as e:
        await websocket.send_json(
            {"status": "error", "code": "SERVER_ERROR", "message": f"Server error: {str(e)}"}
        )
    finally:
        # Let FastAPI close gracefully; explicit close can race the final message in some clients.
        try:
            await websocket.close()
        except Exception:
            pass

@app.get("/download/{session_id}")
async def download_csv(session_id: str):
    # Look up session_id in memory dict
    csv_content = session_storage.get(session_id)
    if not csv_content:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    
    # Return StreamingResponse with Content-Disposition
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads_{session_id}.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
