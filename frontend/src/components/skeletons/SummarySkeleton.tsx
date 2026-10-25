import React from 'react';
import { Skeleton, SkeletonCard } from './SkeletonElements';

export function SummarySkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={140} height={12} borderRadius={3} />
          <Skeleton width={230} height={24} borderRadius={4} />
          <Skeleton width={320} height={13} borderRadius={3} />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Skeleton width={110} height={32} borderRadius={6} />
          <Skeleton width={90} height={32} borderRadius={6} />
        </div>
      </div>

      {/* 4 Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} style={{ padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '70%' }}>
                <Skeleton width="60%" height={11} borderRadius={3} />
                <Skeleton width="85%" height={24} borderRadius={4} />
              </div>
              <Skeleton width={30} height={30} borderRadius={6} />
            </div>
          </SkeletonCard>
        ))}
      </div>

      {/* Narrative Section Card */}
      <div className="card" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Skeleton width={22} height={22} borderRadius={4} />
          <Skeleton width={180} height={18} borderRadius={4} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Skeleton width="100%" height={14} borderRadius={3} />
          <Skeleton width="97%" height={14} borderRadius={3} />
          <Skeleton width="92%" height={14} borderRadius={3} />
          <Skeleton width="65%" height={14} borderRadius={3} />
        </div>
      </div>

      {/* Milestone Cards Timeline */}
      <div className="card" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Skeleton width={160} height={18} borderRadius={4} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3, 4].map((m) => (
            <div
              key={m}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '12px 16px',
                borderRadius: 6,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
              }}
            >
              <Skeleton width={70} height={20} borderRadius={10} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
                <Skeleton width="40%" height={14} borderRadius={3} />
                <Skeleton width="70%" height={12} borderRadius={3} />
              </div>
              <Skeleton width={80} height={20} borderRadius={10} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
