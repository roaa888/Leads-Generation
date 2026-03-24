# AI-powered Lead Generation System

A full-stack multi-agent system that automatically finds B2B sales leads based on user criteria and exports them to a CSV file.

## Tech Stack
- **Frontend:** React + Vite
- **Backend:** FastAPI + Uvicorn
- **Agent Framework:** CrewAI
- **LLM:** Groq API (llama3-70b-8192)
- **Data:** DuckDuckGo, Serper.dev, Hunter.io, BeautifulSoup4

## Setup Instructions

### Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```
5. Configure environment variables:
   ```bash
   cp .env.example .env
   # Open .env and add your API keys:
   # GROQ_API_KEY (https://console.groq.com)
   # HUNTER_API_KEY (https://hunter.io)
   # SERPER_API_KEY (https://serper.dev)
   ```
6. Start the backend server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:5173](http://localhost:5173) in your browser.

## Project Structure
- `backend/`: FastAPI application, multi-agent logic, and tools.
- `frontend/`: React application with real-time status updates via WebSockets.
- `lead-gen/`: Root directory for the combined system.

## Important Rules
- All data is sourced in real-time from the web; no data is hallucinated.
- Leads are deduplicated by company name.
- Emails are validated before export.
- Personal emails take priority over generic ones.
