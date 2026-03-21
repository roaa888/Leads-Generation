import React, { useState, useEffect, useRef } from 'react';
import LeadForm from './components/LeadForm';
import ProgressTracker from './components/ProgressTracker';
import ResultsPanel from './components/ResultsPanel';

function App() {
  const [activeTab, setActiveTab] = useState('Generate Leads');
  const [phase, setPhase] = useState('form'); // 'form' | 'running' | 'done'
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [criteria, setCriteria] = useState(null);
  
  const wsRef = useRef(null);

  const startGeneration = (formData) => {
    setCriteria(formData);
    setPhase('running');
    setActiveTab('Pipeline Progress');
    setCurrentStep(1);
    setError(null);

    const ws = new WebSocket('ws://localhost:8000/ws/generate');
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify(formData));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.step) setCurrentStep(data.step);
      
      if (data.status === 'ready') {
        setResult(data);
        setPhase('done');
        setActiveTab('Results Dashboard');
      }

      if (data.status === 'error') {
        setError(data.message);
        setPhase('done');
        setActiveTab('Results Dashboard');
      }

      if (data.label === "Completed!") {
        setResult((prev) => ({ ...prev, ...data }));
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error.');
      setPhase('done');
      setActiveTab('Results Dashboard');
    };
  };

  const reset = () => {
    setPhase('form');
    setActiveTab('Generate Leads');
    setCurrentStep(0);
    setResult(null);
    setError(null);
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
            <ResultsPanel result={result} error={error} criteria={criteria} onReset={reset} />
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
