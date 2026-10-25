import React from 'react';
import { Skeleton } from './SkeletonElements';

export function TimelineSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Skeleton width={160} height={22} borderRadius={4} />
          <Skeleton width={100} height={20} borderRadius={10} />
          <Skeleton width={80} height={20} borderRadius={10} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Skeleton width={130} height={28} borderRadius={5} />
          <Skeleton width={90} height={28} borderRadius={5} />
        </div>
      </div>

      {/* Main Forensic Cinema Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.8fr', gap: 16 }}>
        {/* Left: Video Player HUD & Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* 16:9 Cinema Canvas */}
          <div
            className="card"
            style={{
              position: 'relative',
              aspectRatio: '16/9',
              width: '100%',
              backgroundColor: '#0c0f11',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: 16,
              border: '1px solid var(--border)',
            }}
          >
            {/* Top HUD Overlays */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Skeleton width={120} height={18} borderRadius={4} />
              <div style={{ display: 'flex', gap: 8 }}>
                <Skeleton width={70} height={18} borderRadius={4} />
                <Skeleton width={60} height={18} borderRadius={4} />
              </div>
            </div>

            {/* Center target indicator */}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <div style={{ width: 120, height: 180, border: '1px dashed var(--border)', borderRadius: 6, position: 'relative' }}>
                <Skeleton width="100%" height="100%" borderRadius={4} />
              </div>
            </div>

            {/* Bottom HUD Overlays */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Skeleton width={140} height={16} borderRadius={4} />
              <Skeleton width={80} height={16} borderRadius={4} />
            </div>
          </div>

          {/* Video Player Control Bar */}
          <div
            className="card"
            style={{
              padding: '10px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              backgroundColor: 'var(--bg-panel)',
            }}
          >
            {/* Timeline Scrubber */}
            <Skeleton width="100%" height={6} borderRadius={3} />
            {/* Playback Controls */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Skeleton width={28} height={28} borderRadius={6} />
                <Skeleton width={24} height={24} borderRadius={4} />
                <Skeleton width={24} height={24} borderRadius={4} />
                <Skeleton width={85} height={16} borderRadius={4} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Skeleton width={70} height={20} borderRadius={4} />
                <Skeleton width={24} height={24} borderRadius={4} />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Selected Event Dossier & Quick Details */}
        <div className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Skeleton width={140} height={18} borderRadius={4} />
            <Skeleton width={60} height={18} borderRadius={10} />
          </div>

          {/* Event thumbnail preview */}
          <Skeleton width="100%" height={140} borderRadius={6} />

          {/* Event details list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[1, 2, 3, 4].map((k) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-dim)' }}>
                <Skeleton width={90} height={12} borderRadius={3} />
                <Skeleton width={110} height={12} borderRadius={3} />
              </div>
            ))}
          </div>

          <Skeleton width="100%" height={32} borderRadius={6} style={{ marginTop: 'auto' }} />
        </div>
      </div>

      {/* Actor ReID Gallery Carousel */}
      <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Skeleton width={18} height={18} borderRadius={4} />
            <Skeleton width={180} height={16} borderRadius={4} />
          </div>
          <Skeleton width={70} height={16} borderRadius={10} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
          {[1, 2, 3, 4, 5, 6].map((p) => (
            <div
              key={p}
              style={{
                padding: 10,
                borderRadius: 6,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <Skeleton width={48} height={48} borderRadius={24} />
              <Skeleton width="80%" height={12} borderRadius={3} />
              <Skeleton width="60%" height={10} borderRadius={3} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
