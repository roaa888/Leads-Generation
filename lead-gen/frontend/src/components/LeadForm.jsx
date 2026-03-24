import React, { useState } from 'react';

const LeadForm = ({ onSubmit }) => {
  const [formData, setFormData] = useState({
    industry: 'SaaS/Software',
    location: '',
    lead_type: 'B2B',
    target_role: 'CEO',
    company_size: '10-50',
    keywords: '',
    num_leads: 10
  });

  const industries = ['SaaS/Software', 'E-commerce', 'Healthcare', 'Real Estate', 'Finance/Fintech', 'Marketing Agency', 'Manufacturing', 'Education', 'Legal', 'Consulting', 'Other'];
  const roles = ['CEO', 'CTO', 'CFO', 'COO', 'CMO', 'Head of Marketing', 'Head of Sales', 'VP of Sales', 'Founder', 'Director', 'Manager'];
  const companySizes = ['1-10', '10-50', '50-200', '200-500', '500+'];
  const leadCounts = [10, 20, 50, 100];

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <div className="form-card">
      <form onSubmit={handleSubmit}>
        <div className="grid-2">
          <div className="field">
            <label className="label">Industry</label>
            <select value={formData.industry} onChange={(e) => setFormData({...formData, industry: e.target.value})}>
              {industries.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>

          <div className="field">
            <label className="label">Location</label>
            <input type="text" placeholder="e.g. United States, London" value={formData.location} onChange={(e) => setFormData({...formData, location: e.target.value})} />
          </div>

          <div className="field">
            <label className="label">Lead Type</label>
            <div className="pill-group">
              {['B2B', 'B2C'].map(t => (
                <button key={t} type="button" className={`pill-btn type ${formData.lead_type === t ? 'active' : ''}`} onClick={() => setFormData({...formData, lead_type: t})}>{t}</button>
              ))}
            </div>
          </div>

          <div className="field">
            <label className="label">Target Role</label>
            <select value={formData.target_role} onChange={(e) => setFormData({...formData, target_role: e.target.value})}>
              {roles.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label">Company Size</label>
            <div className="pill-group">
              {companySizes.map(s => (
                <button key={s} type="button" className={`pill-btn size ${formData.company_size === s ? 'active' : ''}`} onClick={() => setFormData({...formData, company_size: s})}>{s}</button>
              ))}
            </div>
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label">Keywords</label>
            <input type="text" placeholder="Describe specific business model, technology, or niche keywords..." value={formData.keywords} onChange={(e) => setFormData({...formData, keywords: e.target.value})} />
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label">Number of Leads</label>
            <div className="pill-group">
              {leadCounts.map(n => (
                <button key={n} type="button" className={`pill-btn count ${formData.num_leads === n ? 'active' : ''}`} onClick={() => setFormData({...formData, num_leads: n})}>{n} leads</button>
              ))}
            </div>
          </div>
        </div>

        <button type="submit" className="submit-btn" style={{ marginTop: '24px' }}>
          <div className="gem-icon btn"></div>
          Generate {formData.num_leads} Leads
        </button>
      </form>
    </div>
  );
};

export default LeadForm;
