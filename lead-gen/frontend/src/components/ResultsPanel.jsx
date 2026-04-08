import React, { useEffect, useRef } from 'react';

const ResultsPanel = ({ result, error, errorMeta, criteria, onReset, onDownload }) => {
  const donutRef = useRef(null);
  const barRef = useRef(null);
  const lineRef = useRef(null);
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const chartRefs = useRef({ donut: null, bar: null, line: null });

  useEffect(() => {
    if (result && !error) {
      try {
        // Use window.Chart since we included it via script tag
        const Chart = window.Chart;
        if (!Chart) return;

        // Cleanup previous charts (prevents crashes on re-render).
        Object.values(chartRefs.current).forEach((c) => {
          try {
            c?.destroy?.();
          } catch {
            // ignore
          }
        });
        chartRefs.current = { donut: null, bar: null, line: null };

        const total    = Number(result.total_leads ?? 0) || 0;
        const verified = Number(result.verified ?? 0) || 0;
        const missing  = Number(result.missing_email ?? 0) || 0;
        const partial  = Math.max(0, total - verified - missing);
        const preview  = Array.isArray(result.preview) ? result.preview : [];

        // Company-size counts from real preview data
        const sizeCounts = {};
        preview.forEach(r => {
          const sz = r['Company Size'] || 'N/A';
          sizeCounts[sz] = (sizeCounts[sz] || 0) + 1;
        });
        const sizeLabels = Object.keys(sizeCounts);
        const sizeData   = sizeLabels.map(k => sizeCounts[k]);

        // Title distribution from real preview data
        const titleCounts = {};
        preview.forEach(r => {
          const t = r['Title'] && r['Title'] !== 'N/A' ? r['Title'] : 'Unknown';
          titleCounts[t] = (titleCounts[t] || 0) + 1;
        });
        const titleLabels = Object.keys(titleCounts).slice(0, 6);
        const titleData   = titleLabels.map(k => titleCounts[k]);

        // Donut Chart — status breakdown
        chartRefs.current.donut = new Chart(donutRef.current, {
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

        // Bar Chart — company size distribution from real data
        chartRefs.current.bar = new Chart(barRef.current, {
          type: 'bar',
          data: {
            labels: sizeLabels.length ? sizeLabels : ['N/A'],
            datasets: [{
              data: sizeData.length ? sizeData : [0],
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
              x: { grid: { display: false }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 }, maxRotation: 30 } }
            }
          }
        });

        // Bar Chart — contact title distribution from real data
        chartRefs.current.line = new Chart(lineRef.current, {
          type: 'bar',
          data: {
            labels: titleLabels.length ? titleLabels : ['N/A'],
            datasets: [{
              data: titleData.length ? titleData : [0],
              backgroundColor: '#45828b',
              borderRadius: 5
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { grid: { color: '#e0e5e9' }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } },
              y: { grid: { display: false }, ticks: { color: '#45828b', font: { family: 'DM Mono', size: 10 } } }
            }
          }
        });
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Chart render error', e);
      }
    }
  }, [result, error]);

  if (error) {
    return (
      <div className="form-card" style={{ textAlign: 'center', color: 'var(--text)' }}>
        <h2 style={{ color: 'var(--dark)', marginBottom: '12px' }}>Generation Failed</h2>
        <p style={{ color: 'var(--text2)', marginBottom: '24px' }}>{error}</p>
        {(errorMeta?.code || errorMeta?.details) && (
          <div style={{ textAlign: 'left', background: 'rgba(5, 91, 101, 0.06)', borderRadius: '12px', padding: '12px', marginBottom: '16px' }}>
            {errorMeta?.code && (
              <div style={{ fontSize: '11px', color: 'var(--text2)', marginBottom: '6px' }}>
                Code: <span style={{ color: 'var(--dark)' }}>{errorMeta.code}</span>
              </div>
            )}
            {errorMeta?.details && (
              <div style={{ fontSize: '11px', color: 'var(--text2)', whiteSpace: 'pre-wrap' }}>
                {String(errorMeta.details)}
              </div>
            )}
          </div>
        )}
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

  // Debug log
  // eslint-disable-next-line no-console
  console.log("ResultsPanel props:", { result, error, errorMeta, criteria });

  const sessionId = result?.session_id;
  const totalLeads = Number(result?.total_leads ?? 0) || 0;
  const verified = Number(result?.verified ?? 0) || 0;
  const missingEmail = Number(result?.missing_email ?? 0) || 0;
  const preview = Array.isArray(result?.preview) ? result.preview : [];

  return (
    <div className="dashboard-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div style={{ fontSize: '13px', fontWeight: 500 }}>
          Results — {criteria?.industry} / {criteria?.location} / {criteria?.target_role}
        </div>
        <button
          className="submit-btn"
          style={{ width: 'auto', padding: '8px 16px', fontSize: '11px' }}
          onClick={onDownload}
          disabled={!sessionId}
          title={!sessionId ? 'No session id yet' : 'Download CSV'}
        >
          ⬇ Download leads.xlsx
        </button>
      </div>

      <div className="stat-cards">
        <div className="stat-card" style={{ borderTopColor: '#055b65' }}>
          <span className="stat-val">{totalLeads}</span>
          <span className="stat-label">Total Leads</span>
          <span className="stat-detail">Found from sources</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#1bd488' }}>
          <span className="stat-val">{verified}</span>
          <span className="stat-label">Verified</span>
          <span className="stat-detail">Direct contact found</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#45828b' }}>
          <span className="stat-val">{Math.max(0, totalLeads - verified - missingEmail)}</span>
          <span className="stat-label">Partial</span>
          <span className="stat-detail">General emails only</span>
        </div>
        <div className="stat-card" style={{ borderTopColor: '#b2c9c5' }}>
          <span className="stat-val">{missingEmail}</span>
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
        <div className="chart-title">Contact Title Distribution</div>
        <div style={{ height: '200px' }}>
          <canvas ref={lineRef}></canvas>
        </div>
      </div>

      <div className="table-card">
          <div className="table-header-bar">
            <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text2)', letterSpacing: '0.8px' }}>
            All Leads ({totalLeads})
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
                <th>LinkedIn</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((row, idx) => (
                <tr key={idx}>
                  <td>{row['Company Name']}</td>
                  <td>{row['Contact Name']}</td>
                  <td>{row['Title']}</td>
                  <td>{row['Email']}</td>
                  <td>{row['Phone']}</td>
                  <td>{row['Location']}</td>
                  <td>{row['Company Size']}</td>
                  <td>
                    {row['LinkedIn'] && row['LinkedIn'] !== 'N/A' ? (
                      <a href={row['LinkedIn']} target="_blank" rel="noopener noreferrer"
                         style={{ color: '#0A66C2', fontWeight: 600, fontSize: '11px', textDecoration: 'none' }}
                         title={row['LinkedIn']}>
                        in
                      </a>
                    ) : (
                      <span style={{ color: 'var(--muted)', fontSize: '10px' }}>—</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${(row['Status'] || '').toLowerCase().replace(' ', '')}`}>
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
