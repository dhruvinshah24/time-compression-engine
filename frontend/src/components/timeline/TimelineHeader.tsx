'use client';

import React from 'react';
import Link from 'next/link';
import { FileText, Download, ChevronDown, User } from 'lucide-react';

interface TimelineHeaderProps {
  videoId: string;
  filename: string;
  duration: number;
  data: any;
  fmtSecOnly: (sec: number) => string;
}

export function TimelineHeader({
  videoId,
  filename,
  duration,
  data,
  fmtSecOnly,
}: TimelineHeaderProps) {
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `TCE_manifest_${videoId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 sm:gap-4">
      <div>
        {/* Breadcrumb */}
        <div style={{
          fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
          marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
        }}>
          <Link href="/timeline" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Recordings</Link>
          <span>/</span>
          <span style={{ color: 'var(--text-secondary)' }}>{filename}</span>
        </div>

        {/* Title + Status Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{
            fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            Forensic Timeline
          </h1>

          {/* Analyzed Badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '3px 8px', borderRadius: 4,
            backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
          }}>
            <span style={{ display: 'flex', gap: 3 }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
              <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
            </span>
            <span>Analyzed ({fmtSecOnly(duration)})</span>
          </div>

          {/* Resolution / Format Pill */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '3px 10px', borderRadius: 4,
            backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)',
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
          }}>
            <span>{data.metadata?.resolution || '1080p'} • {data.metadata?.fps ? `${Math.round(data.metadata.fps)} FPS` : 'H.264'}</span>
          </div>
        </div>
      </div>

      {/* Right Header Action Buttons */}
      <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
        <Link
          href={`/summary/${videoId}`}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <FileText size={13} style={{ color: 'var(--text-secondary)' }} />
          <span>Executive Summary</span>
        </Link>

        <button
          onClick={handleExport}
          className="btn btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px' }}
        >
          <Download size={13} style={{ color: 'var(--text-secondary)' }} />
          <span>Export</span>
          <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} />
        </button>

        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-secondary)'
        }}>
          <User size={15} />
        </div>
      </div>
    </div>
  );
}

