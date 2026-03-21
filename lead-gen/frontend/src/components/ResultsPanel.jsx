import React, { useEffect, useRef } from 'react';

const ResultsPanel = ({ result, error, criteria, onReset }) => {
  const donutRef = useRef(null);
  const barRef = useRef(null);
  const lineRef = useRef(null);

  useEffect(() => {
    if (result && !error) {
      // Use window.Chart since we included it via script tag
      const Chart = window.Chart;
      if (!Chart) return;

      const total = result.total_leads || 10;
      const verified = result.verified || 0;
      const missing = result.missing_email || 0;
      const partial = total - verified - missing;

      // Donut Chart
      new Chart(donutRef.current, {
        type: 'doughnut',
        data: {
          labels: ['Verified', 'Partial', 'Missing'],
          datasets: [{
            data: [verified, partial, missing],
            backgroundColor: ['#1bd488', '#45828b', '#b2c9c5'],
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          cutout: '65%',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } }
        }
      });

      // Bar Chart
      new Chart(barRef.current, {
        type: 'bar',
        data: {
          labels: ['1-10', '10-50', '50-200', '200-500', '500+'],
          datasets: [{
            data: [2, 5, 3, 1, 0], // Sample data
            backgroundColor: '#055b65',
            borderRadius: 5
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { grid: { color: '#e0e5e9' }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } },
            x: { grid: { display: false }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } }
          }
        }
      });

      // Line Chart
      new Chart(lineRef.current, {
        type: 'line',
        data: {
          labels: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'],
          datasets: [
            {
              label: 'Found',
              data: [4, 8, 15, 12, 20],
              borderColor: '#1bd488',
              backgroundColor: 'rgba(27, 212, 136, 0.08)',
              fill: true,
              tension: 0.4,
              pointRadius: 4
            },
            {
              label: 'Verified',
              data: [2, 5, 10, 8, 15],
              borderColor: '#45828b',
              backgroundColor: 'rgba(69, 130, 139, 0.06)',
              fill: true,
              tension: 0.4,
              pointRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { grid: { color: '#e0e5e9' }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } },
            x: { grid: { display: false }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } }
          }
        }
      });
    }
  }, [result, error]);

  if (error) {
    return (
      <div className="form-card" style={{ textAlign: 'center', color: 'var(--text)' }}>
        <h2 style={{ color: 'var(--dark)', marginBottom: '12px' }}>Generation Failed</h2>
        <p style={{ color: 'var(--text2)', marginBottom: '24px' }}>{error}</p>
        <button className="submit-btn" onClick={onReset}>Try Again</button>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="form-card" style={{ textAlign: 'center', color: 'var(--muted)' }}>
        <p>No results yet. Start a generation to see data here.</p>
      </div>
    );
  }

  const { session_id, total_leads, verified, missing_email, preview } = result;

  return (
    <div className="dashboard-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div style={{ fontSize: '13px', fontWeight: 500 }}>
          Results — {criteria?.industry} / {criteria?.location} / {criteria?.target_role}
        </div>
        <a href={`http://localhost:8000/download/${session_id}`} className="submit-btn" style={{ width: 'auto', padding: '8px 16px', fontSize: '11px' }}>
          ⬇ Download leads.csv
        </a>
      </div>

      <div className="stat-cards">
        <div className="stat-card" style={{ borderTopColor: '#055b65' }}>
          <span className="stat-val">{total_leads}</span>
          <span className="stat-label">Total Leads</span>
          <span className="stat-detail">Found from sources</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#1bd488' }}>
          <span className="stat-val">{verified}</span>
          <span className="stat-label">Verified</span>
          <span className="stat-detail">Direct contact found</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#45828b' }}>
          <span className="stat-val">{total_leads - verified - missing_email}</span>
          <span className="stat-label">Partial</span>
          <span className="stat-detail">General emails only</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#b2c9c5' }}>
          <span className="stat-val">{missing_email}</span>
          <span className="stat-label">Missing</span>
          <span className="stat-detail">No email found</span>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-title">Lead Status Breakdown</div>
          <div style={{ height: '180px', position: 'relative' }}>
            <canvas ref={donutRef}></canvas>
          </div>
          <div style={{ display: 'flex', gap: '12px', marginTop: '12px', justifyContent: 'center' }}>
            <div className="legend-item"><div className="legend-color" style={{ background: '#1bd488' }}></div>Verified</div>
            <div className="legend-item"><div className="legend-color" style={{ background: '#45828b' }}></div>Partial</div>
            <div className="legend-item"><div className="legend-color" style={{ background: '#b2c9c5' }}></div>Missing</div>
          </div>
        </div>
        <div className="chart-card">
          <div className="chart-title">Company Size Distribution</div>
          <div style={{ height: '180px' }}>
            <canvas ref={barRef}></canvas>
          </div>
        </div>
      </div>

      <div className="chart-card" style={{ marginBottom: '16px' }}>
        <div className="chart-title">Leads Found per Search Query</div>
        <div style={{ height: '200px' }}>
          <canvas ref={lineRef}></canvas>
        </div>
      </div>

      <div className="table-card">
        <div className="table-header-bar">
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text2)', letterSpacing: '0.8px' }}>
            All Leads ({total_leads})
          </div>
          <div style={{ color: 'var(--green)', fontSize: '11px' }}>● Pipeline complete</div>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Contact</th>
                <th>Title</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Location</th>
                <th>Size</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview?.map((row, idx) => (
                <tr key={idx}>
                  <td>{row['Company Name']}</td>
                  <td>{row['Contact Name']}</td>
                  <td>{row['Title']}</td>
                  <td>{row['Email']}</td>
                  <td>{row['Phone']}</td>
                  <td>{row['Location']}</td>
                  <td>{row['Company Size']}</td>
                  <td>
                    <span className={`badge ${row['Status'].toLowerCase().replace(' ', '')}`}>
                      {row['Status']}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      <div style={{ textAlign: 'center', marginTop: '24px' }}>
        <button className="pill-btn size" onClick={onReset}>Generate New Leads</button>
      </div>
    </div>
  );
};

export default ResultsPanel;
