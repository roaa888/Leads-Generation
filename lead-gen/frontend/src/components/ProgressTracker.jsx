import React from 'react';

const ProgressTracker = ({ currentStep, phase, onPreview }) => {
  const steps = [
    { id: 1, label: "Search", desc: "Finding companies via DuckDuckGo & Serper" },
    { id: 2, label: "Enrich", desc: "Scraped websites — phone, location extracted" },
    { id: 3, label: "Contact", desc: "Calling Hunter.io + scraping contact pages..." },
    { id: 4, label: "Validate", desc: "Cleaning & deduplicating data" },
    { id: 5, label: "Export", desc: "Building your CSV file" },
    { id: 6, label: "Complete", desc: "Your leads are ready!" }
  ];

  return (
    <div className="tracker-container">
      <div className="gem-icon spinner" style={{ margin: '0 auto 24px' }}></div>
      <h2 style={{ fontSize: '24px', marginBottom: '4px' }}>Agents are working...</h2>
      <p style={{ fontSize: '12px', color: 'var(--text2)' }}>
        {steps.find(s => s.id === currentStep)?.label || "Initializing..."}
      </p>

      <div className="vertical-track">
        {steps.map((step) => {
          const isDone = currentStep > step.id || (phase === 'done' && currentStep === 6);
          const isActive = currentStep === step.id && phase !== 'done';
          return (
            <div key={step.id} className={`step-row ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}>
              <div className="step-indicator-container">
                <div className={`step-dot ${isDone ? 'done' : (isActive ? 'active' : '')}`}>
                  {isDone ? '✓' : step.id}
                </div>
                <div className={`connector ${isDone ? 'done' : ''}`}></div>
              </div>
              <div className="step-content">
                <div className="step-name">{step.label}</div>
                <div className="step-desc">{step.desc}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-bar-bg">
        <div className="progress-bar-fill" style={{ width: `${(Math.max(0, currentStep - 1) / 5) * 100}%` }}></div>
      </div>
      
      {phase === 'done' && (
        <button className="pill-btn size" style={{ marginTop: '24px' }} onClick={onPreview}>
          View Results Dashboard
        </button>
      )}
    </div>
  );
};

export default ProgressTracker;
