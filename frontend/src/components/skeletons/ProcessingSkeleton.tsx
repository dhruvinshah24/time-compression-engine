import React from 'react';
import { Skeleton } from './SkeletonElements';

export function ProcessingSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Skeleton width={180} height={24} borderRadius={4} />
            <Skeleton width={80} height={20} borderRadius={10} />
          </div>
          <Skeleton width={300} height={13} borderRadius={3} />
        </div>
        <Skeleton width={120} height={28} borderRadius={5} />
      </div>

      {/* Progress Card */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Skeleton width={140} height={14} borderRadius={3} />
          <Skeleton width={50} height={14} borderRadius={3} />
        </div>
        <Skeleton width="100%" height={8} borderRadius={4} />
      </div>

      {/* 12-Stage Stepper Grid */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Skeleton width={180} height={16} borderRadius={4} />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((st) => (
            <div
              key={st}
              style={{
                padding: '10px 12px',
                borderRadius: 6,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Skeleton width={20} height={20} borderRadius={10} />
                <Skeleton width={100} height={13} borderRadius={3} />
              </div>
              <Skeleton width={50} height={16} borderRadius={8} />
            </div>
          ))}
        </div>
      </div>

      {/* Terminal Log Console */}
      <div
        className="card"
        style={{
          padding: 16,
          backgroundColor: '#0a0d0e',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          border: '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <Skeleton width={12} height={12} borderRadius={6} />
          <Skeleton width={100} height={14} borderRadius={3} />
        </div>
        {[90, 80, 95, 70, 85, 60].map((w, idx) => (
          <Skeleton key={idx} width={`${w}%`} height={12} borderRadius={2} />
        ))}
      </div>
    </div>
  );
}
