import React from 'react';
import { Cpu, Radio } from 'lucide-react';

export default function ProcessingLoading() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      width: '100%',
      padding: 24,
      textAlign: 'center'
    }}>
      <div className="card" style={{
        maxWidth: 480,
        width: '100%',
        padding: '36px 28px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 18,
        border: '1px solid var(--border)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      }}>
        {/* Animated Radar Pulse */}
        <div style={{
          position: 'relative',
          width: 64,
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            backgroundColor: 'var(--accent-bg)',
            border: '2px solid var(--accent)',
            animation: 'ping 1.6s cubic-bezier(0, 0, 0.2, 1) infinite',
            opacity: 0.4,
          }} />
          <div style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            backgroundColor: 'var(--accent-bg)',
            border: '1px solid var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent)',
            zIndex: 1,
          }}>
            <Cpu size={24} style={{ animation: 'spin 4s linear infinite' }} />
          </div>
        </div>

        <div>
          <div style={{
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            color: 'var(--accent)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6
          }}>
            <Radio size={12} className="pulse" />
            <span>Connecting To Pipeline Engine</span>
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Mounting Live Pipeline Telemetry
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
            Synchronizing execution state across all 12 neural processing stages...
          </p>
        </div>

        {/* Indeterminate scanning bar */}
        <div className="progress-track" style={{ height: 4, width: '80%', overflow: 'hidden' }}>
          <div style={{
            width: '45%',
            height: '100%',
            backgroundColor: 'var(--accent)',
            borderRadius: 2,
            animation: 'indeterminate 1.4s ease-in-out infinite alternate',
          }} />
        </div>
      </div>
    </div>
  );
}
