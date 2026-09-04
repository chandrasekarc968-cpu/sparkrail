import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ThreeDErrorBoundaryProps {
  children: ReactNode;
  onFallbackTo2D?: () => void;
}

interface ThreeDErrorBoundaryState {
  hasError: boolean;
  errorMessage: string;
}

export class ThreeDErrorBoundary extends Component<ThreeDErrorBoundaryProps, ThreeDErrorBoundaryState> {
  constructor(props: ThreeDErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      errorMessage: ''
    };
  }

  static getDerivedStateFromError(error: Error): ThreeDErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || 'WebGL 3D Scene encountered an unrecoverable rendering error.'
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ThreeDErrorBoundary caught a WebGL/Three.js error:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, errorMessage: '' });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            padding: '24px'
          }}
        >
          <div
            style={{
              maxWidth: '520px',
              backgroundColor: '#1e293b',
              border: '1px solid #ef4444',
              borderRadius: '8px',
              padding: '28px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>⚠️</div>
            <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 800, color: '#ef4444' }}>
              3D WebGL Initialization Failure
            </h3>
            <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, margin: '0 0 16px 0' }}>
              The WebGL scene encountered a hardware or rendering context error:
            </p>
            <pre
              style={{
                backgroundColor: '#0f172a',
                padding: '10px 14px',
                borderRadius: '6px',
                border: '1px solid #334155',
                fontSize: '11px',
                fontFamily: 'monospace',
                color: '#fca5a5',
                textAlign: 'left',
                overflowX: 'auto',
                marginBottom: '20px'
              }}
            >
              {this.state.errorMessage}
            </pre>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
              <button
                onClick={this.handleRetry}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 700,
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                🔄 Retry WebGL Scene
              </button>
              {this.props.onFallbackTo2D && (
                <button
                  onClick={this.props.onFallbackTo2D}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#334155',
                    color: '#f8fafc',
                    border: '1px solid #475569',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  🗺️ Switch to 2D Schematic
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
