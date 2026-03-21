import uuid
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import io

from models import SearchCriteria
from orchestrator import LeadOrchestrator

app = FastAPI()

# Store CSV strings in memory dict keyed by session_id
session_storage = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.websocket("/ws/generate")
async def generate_leads(websocket: WebSocket):
    await websocket.accept()
    try:
        # Receive JSON -> parse as SearchCriteria
        data = await websocket.receive_json()
        criteria = SearchCriteria(**data)
        
        # Generate session_id (uuid4)
        session_id = str(uuid.uuid4())
        
        # Call run_pipeline(criteria, websocket)
        orchestrator = LeadOrchestrator(criteria, websocket)
        csv_data = await orchestrator.run_pipeline()
        
        if csv_data:
            # Store CSV string in memory
            session_storage[session_id] = csv_data
            
            # Send: {status:"ready", session_id, message}
            await websocket.send_json({
                "status": "ready",
                "session_id": session_id,
                "message": "Leads generated successfully!"
            })
        else:
            await websocket.send_json({
                "status": "error",
                "message": "Pipeline failed to generate leads."
            })
            
    except ValidationError as e:
        await websocket.send_json({"status": "error", "message": f"Invalid criteria: {str(e)}"})
    except Exception as e:
        await websocket.send_json({"status": "error", "message": f"An unexpected error occurred: {str(e)}"})
    finally:
        await websocket.close()

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
