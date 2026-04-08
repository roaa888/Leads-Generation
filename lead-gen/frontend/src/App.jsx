import React, { useState, useEffect, useRef } from 'react';
import LeadForm from './components/LeadForm';
import ProgressTracker from './components/ProgressTracker';
import ResultsPanel from './components/ResultsPanel';
import HistoryPanel from './components/HistoryPanel';
import ErrorBoundary from './components/ErrorBoundary';

// Use relative paths so all requests route through the Vite proxy (works in WSL2 and production).
// Override via VITE_API_URL / VITE_WS_URL if you need to point at a remote backend.
const apiBase = import.meta.env.VITE_API_URL || '';
const wsUrl = (() => {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/generate`;
})();

function App() {
  const [activeTab, setActiveTab]   = useState('Generate Leads');
  const [phase, setPhase]           = useState('form'); // 'form' | 'running' | 'done'
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult]         = useState(null);
  const [prefill, setPrefill]       = useState(null);  // criteria prefilled from history re-run
  const [error, setError] = useState(null);
  const [errorMeta, setErrorMeta] = useState(null);
  const [criteria, setCriteria] = useState(null);
  
  const wsRef = useRef(null);
  const gotWsMessageRef = useRef(false);
  const statusPollRef = useRef(null);

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
      setError('Backend not reachable. Make sure the backend is running: cd lead-gen/backend && uvicorn main:app --host 127.0.0.1 --port 8000');
      setErrorMeta({
        code: 'BACKEND_UNREACHABLE',
        details: 'Health check at /health failed after retries. Start the backend with: uvicorn main:app --host 127.0.0.1 --port 8000',
      });
      setPhase('done');
      setActiveTab('Results Dashboard');
      return;
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    gotWsMessageRef.current = false;
    if (statusPollRef.current) clearInterval(statusPollRef.current);
    statusPollRef.current = null;

    ws.onopen = () => {
      ws.send(JSON.stringify(formData));
    };

    const finishWithResult = (data) => {
      if (statusPollRef.current) { clearInterval(statusPollRef.current); statusPollRef.current = null; }
      setResult(data);
      setPhase('done');
      setActiveTab('Results Dashboard');
    };

    const finishWithError = (data) => {
      if (statusPollRef.current) { clearInterval(statusPollRef.current); statusPollRef.current = null; }
      setError(data.message || data.label || 'An unexpected error occurred during lead generation.');
      setErrorMeta({ code: data.code, details: data.details });
      setPhase('done');
      setActiveTab('Results Dashboard');
    };

    ws.onmessage = (event) => {
      gotWsMessageRef.current = true;
      const data = JSON.parse(event.data);
      if (data.step) setCurrentStep(data.step);

      if (data.status === 'started' && data.session_id) {
        setResult((prev) => ({ ...(prev || {}), session_id: data.session_id, status: 'running' }));
        statusPollRef.current = setInterval(async () => {
          try {
            const res = await fetch(`${apiBase}/status/${data.session_id}`);
            if (!res.ok) return;
            const st = await res.json();
            if (st.status === 'ready') finishWithResult(st);
            else if (st.status === 'error') finishWithError(st);
          } catch { /* ignore polling errors */ }
        }, 1500);
      }

      if (data.status === 'ready') finishWithResult(data);

      if (data.status === 'error' || (data.step === 0 && (data.code || data.details))) {
        finishWithError(data);
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

  const handleDownload = async () => {
    const sessionId = result?.session_id;
    if (!sessionId) return;
    const url = `${apiBase}/download/${sessionId}`;
    // eslint-disable-next-line no-console
    console.log("Download URL:", url);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    const blob = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'leads.xlsx';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  };

  const reset = () => {
    if (statusPollRef.current) clearInterval(statusPollRef.current);
    statusPollRef.current = null;
    setPhase('form');
    setActiveTab('Generate Leads');
    setCurrentStep(0);
    setResult(null);
    setError(null);
    setErrorMeta(null);
  };

  return (
    <ErrorBoundary>
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
        {['Generate Leads', 'Pipeline Progress', 'Results Dashboard', 'Previous Leads'].map(tab => (
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
            <LeadForm onSubmit={startGeneration} prefill={prefill} />
          </div>
        )}

        {activeTab === 'Pipeline Progress' && (
          <div className="tab-content">
            <ProgressTracker currentStep={currentStep} phase={phase} onPreview={() => setActiveTab('Results Dashboard')} />
          </div>
        )}

        {activeTab === 'Results Dashboard' && (
          <div className="tab-content">
            <ResultsPanel result={result} error={error} errorMeta={errorMeta} criteria={criteria} onReset={reset} onDownload={handleDownload} />
          </div>
        )}

        {activeTab === 'Previous Leads' && (
          <div className="tab-content">
            <HistoryPanel onRerun={(savedCriteria) => {
              setPrefill(savedCriteria);
              setActiveTab('Generate Leads');
            }} />
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
    </ErrorBoundary>
  );
}

export default App;
