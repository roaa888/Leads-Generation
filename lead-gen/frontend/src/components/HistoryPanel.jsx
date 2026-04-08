import React, { useEffect, useState, useCallback } from 'react';

const apiBase = import.meta.env.VITE_API_URL || '';

const fmt = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    + ' · '
    + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};

const HistoryPanel = ({ onRerun }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/history`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setSessions(json.sessions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDownload = async (sessionId) => {
    const res = await fetch(`${apiBase}/download/${sessionId}`);
    if (!res.ok) return;
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href     = URL.createObjectURL(blob);
    link.download = `leads_${sessionId.slice(0, 8)}.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  };

  if (loading) {
    return (
      <div className="form-card" style={{ textAlign: 'center', color: 'var(--muted)' }}>
        <p>Loading history…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="form-card" style={{ textAlign: 'center' }}>
        <p style={{ color: 'var(--text2)', marginBottom: '12px' }}>Could not load history: {error}</p>
        <button className="pill-btn size" onClick={load}>Retry</button>
      </div>
    );
  }

  if (!sessions.length) {
    return (
      <div className="form-card" style={{ textAlign: 'center', color: 'var(--muted)' }}>
        <p>No previous sessions yet. Generate leads to see history here.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--dark)' }}>
          {sessions.length} saved session{sessions.length !== 1 ? 's' : ''}
        </span>
        <button className="pill-btn size" onClick={load} style={{ fontSize: '10px', padding: '4px 10px' }}>
          Refresh
        </button>
      </div>

      {sessions.map((s) => {
        const isOpen = expanded === s.session_id;
        const preview = Array.isArray(s.preview) ? s.preview : [];
        const verifiedPct = s.total_leads ? Math.round((s.verified / s.total_leads) * 100) : 0;

        return (
          <div key={s.session_id} className="table-card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* ── Header row ── */}
            <div
              style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '14px 16px', cursor: 'pointer',
                background: isOpen ? 'rgba(5,91,101,0.04)' : 'transparent',
              }}
              onClick={() => setExpanded(isOpen ? null : s.session_id)}
            >
              {/* Chevron */}
              <span style={{ color: 'var(--dark)', fontSize: '10px', minWidth: '10px' }}>
                {isOpen ? '▼' : '▶'}
              </span>

              {/* Date */}
              <span style={{ fontSize: '10px', color: 'var(--muted)', minWidth: '140px' }}>
                {fmt(s.created_at)}
              </span>

              {/* Criteria tags */}
              <div style={{ display: 'flex', gap: '6px', flex: 1, flexWrap: 'wrap' }}>
                {[s.industry, s.location, s.target_role].filter(Boolean).map((tag) => (
                  <span key={tag} style={{
                    background: 'rgba(5,91,101,0.08)', color: 'var(--dark)',
                    borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 500,
                  }}>{tag}</span>
                ))}
              </div>

              {/* Stats */}
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginLeft: 'auto' }}>
                <span style={{ fontSize: '11px', color: 'var(--text2)' }}>
                  <strong style={{ color: 'var(--dark)' }}>{s.total_leads}</strong> leads
                </span>
                <span style={{ fontSize: '11px', color: '#1bd488', fontWeight: 600 }}>
                  {verifiedPct}% verified
                </span>
                <span className="badge verified" style={{ fontSize: '9px' }}>
                  {s.verified}✓
                </span>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '8px' }} onClick={(e) => e.stopPropagation()}>
                <button
                  className="pill-btn size"
                  style={{ fontSize: '10px', padding: '4px 10px' }}
                  onClick={() => handleDownload(s.session_id)}
                  title="Download Excel"
                >
                  ⬇ .xlsx
                </button>
                {onRerun && (
                  <button
                    className="pill-btn size"
                    style={{ fontSize: '10px', padding: '4px 10px', background: 'var(--dark)', color: '#fff' }}
                    onClick={() => onRerun({
                      industry:     s.industry     || '',
                      location:     s.location     || '',
                      target_role:  s.target_role  || 'CEO',
                      company_size: s.company_size || '10-50',
                      lead_type:    s.lead_type    || 'B2B',
                      keywords:     s.keywords     || '',
                      num_leads:    s.num_leads    || 10,
                    })}
                    title="Re-run with same criteria"
                  >
                    ↺ Re-run
                  </button>
                )}
              </div>
            </div>

            {/* ── Expanded preview table ── */}
            {isOpen && preview.length > 0 && (
              <div style={{ borderTop: '1px solid var(--border)', overflowX: 'auto' }}>
                <table style={{ fontSize: '10px' }}>
                  <thead>
                    <tr>
                      {['Company', 'Contact', 'Title', 'Email', 'Phone', 'Location', 'Status'].map(h => (
                        <th key={h} style={{ background: 'rgba(5,91,101,0.07)', fontSize: '9px' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        <td>{row['Company Name']}</td>
                        <td>{row['Contact Name']}</td>
                        <td>{row['Title']}</td>
                        <td>{row['Email']}</td>
                        <td>{row['Phone']}</td>
                        <td>{row['Location']}</td>
                        <td>
                          <span className={`badge ${(row['Status'] || '').toLowerCase().replace(' ', '')}`}
                                style={{ fontSize: '8px' }}>
                            {row['Status']}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {preview.length > 5 && (
                  <div style={{ padding: '6px 16px', fontSize: '10px', color: 'var(--muted)' }}>
                    + {preview.length - 5} more rows in the download
                  </div>
                )}
              </div>
            )}

            {isOpen && preview.length === 0 && (
              <div style={{ padding: '10px 16px', fontSize: '11px', color: 'var(--muted)',
                            borderTop: '1px solid var(--border)' }}>
                No preview available — download the file to view leads.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default HistoryPanel;
