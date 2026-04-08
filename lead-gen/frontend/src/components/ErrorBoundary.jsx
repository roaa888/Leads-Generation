import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error('UI crashed:', error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="form-card" style={{ marginTop: '48px', maxWidth: '860px' }}>
          <h2 style={{ color: 'var(--dark)', marginBottom: '12px' }}>UI Error</h2>
          <p style={{ color: 'var(--text2)', marginBottom: '12px' }}>
            The app crashed while rendering. Check the details below.
          </p>
          <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap', color: 'var(--text)' }}>
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button className="submit-btn" style={{ marginTop: '16px' }} onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

