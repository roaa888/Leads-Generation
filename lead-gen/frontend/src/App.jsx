import React, { useState, useEffect, useRef } from 'react';
import LeadForm from './components/LeadForm';
import ProgressTracker from './components/ProgressTracker';
import ResultsPanel from './components/ResultsPanel';

const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/generate';

function App() {
  const [activeTab, setActiveTab] = useState('Generate Leads');
  const [phase, setPhase] = useState('form'); // 'form' | 'running' | 'done'
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [errorMeta, setErrorMeta] = useState(null);
  const [criteria, setCriteria] = useState(null);
  
  const wsRef = useRef(null);
  const gotWsMessageRef = useRef(false);

  const waitForBackend = async () => {
    // Backend can take a few seconds to boot (imports, CrewAI, etc.).
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(`${apiBase}/health`, { signal: controller.signal });
        clearTimeout(timeout);
        if (res.ok) return true;
      } catch {
        // ignore and retry
      }
      await new Promise(r => setTimeout(r, 800));
    }
    return false;
  };

  const startGeneration = async (formData) => {
    setCriteria(formData);
    setPhase('running');
    setActiveTab('Pipeline Progress');
    setCurrentStep(1);
    setError(null);
    setErrorMeta(null);

    // Quick connectivity check so we can surface a useful UI error when backend isn't reachable.
    const ok = await waitForBackend();
    if (!ok) {
      setError(`Backend not reachable from the browser at ${apiBase}. This is often caused by CORS/origin mismatch (not the server being down).`);
      setErrorMeta({
        code: 'BACKEND_UNREACHABLE',
        details: `Health check failed after retries. If you can open ${apiBase}/health in the browser, restart the backend and ensure CORS allows your frontend origin (e.g. http://localhost:5173, http://127.0.0.1:5173, http://wsl.localhost:5173).`,
      });
      setPhase('done');
      setActiveTab('Results Dashboard');
      return;
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    gotWsMessageRef.current = false;

    ws.onopen = () => {
      ws.send(JSON.stringify(formData));
    };

    ws.onmessage = (event) => {
      gotWsMessageRef.current = true;
      const data = JSON.parse(event.data);
      if (data.step) setCurrentStep(data.step);
      
      if (data.status === 'ready') {
        setResult(data);
        setPhase('done');
        setActiveTab('Results Dashboard');
      }

      if (data.status === 'error') {
        setError(data.message || data.label || 'An unexpected error occurred during lead generation.');
        setErrorMeta({ code: data.code, details: data.details });
        setPhase('done');
        setActiveTab('Results Dashboard');
      }

      // Orchestrator may emit step=0 errors without the outer wrapper.
      if (data.step === 0 && (data.status === 'error' || data.code || data.details)) {
        setError(data.message || data.label || 'Pipeline error.');
        setErrorMeta({ code: data.code, details: data.details });
        setPhase('done');
        setActiveTab('Results Dashboard');
      }

      if (data.label === "Completed!") {
        setResult((prev) => ({ ...prev, ...data }));
      }
    };

    ws.onerror = () => {
      setError(`WebSocket connection error. Could not connect to ${wsUrl}.`);
      setErrorMeta({ code: 'WS_ERROR' });
      setPhase('done');
      setActiveTab('Results Dashboard');
    };

    ws.onclose = (event) => {
      // Normal behavior: backend closes the socket after sending final status.
      // Only show an error if the socket closes without delivering any messages.
      if (!gotWsMessageRef.current) {
        setError(`WebSocket closed before receiving any data (code ${event.code}).`);
        setErrorMeta({ code: 'WS_CLOSED', details: event.reason || 'No close reason provided.' });
        setPhase('done');
        setActiveTab('Results Dashboard');
      }
    };
  };

  const reset = () => {
    setPhase('form');
    setActiveTab('Generate Leads');
    setCurrentStep(0);
    setResult(null);
    setError(null);
    setErrorMeta(null);
  };

  return (
    <div className="app-shell">
      <header>
        <div className="logo-container">
          <div className="gem-icon logo"></div>
          <span className="logo-text">Ready2Start</span>
        </div>
        <div className="header-center">AI-POWERED LEAD GENERATION</div>
        <div className="cost-badge">Total Cost: $0</div>
      </header>

      <nav className="tab-nav">
        {['Generate Leads', 'Pipeline Progress', 'Results Dashboard'].map(tab => (
          <div 
            key={tab} 
            className={`tab-item ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </div>
        ))}
      </nav>

      <main>
        {activeTab === 'Generate Leads' && (
          <div className="tab-content">
            <div className="hero-section">
              <h1 className="hero-title">Find your perfect leads</h1>
              <p className="hero-subtitle">Describe your ideal customer...</p>
            </div>
            <LeadForm onSubmit={startGeneration} />
          </div>
        )}

        {activeTab === 'Pipeline Progress' && (
          <div className="tab-content">
            <ProgressTracker currentStep={currentStep} phase={phase} onPreview={() => setActiveTab('Results Dashboard')} />
          </div>
        )}

        {activeTab === 'Results Dashboard' && (
          <div className="tab-content">
            <ResultsPanel result={result} error={error} errorMeta={errorMeta} criteria={criteria} onReset={reset} />
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="footer-left">
          CrewAI · Groq LLaMA 3 · Hunter.io · DuckDuckGo · Serper.dev · BeautifulSoup4
        </div>
        <div className="footer-right">$0 / month</div>
      </footer>
    </div>
  );
}

export default App;
