import React from 'react';
import { Skeleton, SkeletonCard } from './SkeletonElements';

export function StoriesSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={140} height={12} borderRadius={3} />
          <Skeleton width={210} height={24} borderRadius={4} />
          <Skeleton width={360} height={13} borderRadius={3} />
        </div>
        <Skeleton width={110} height={28} borderRadius={5} />
      </div>

      {/* Summary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '70%' }}>
                <Skeleton width="55%" height={11} borderRadius={3} />
                <Skeleton width="80%" height={22} borderRadius={4} />
              </div>
              <Skeleton width={28} height={28} borderRadius={6} />
            </div>
          </SkeletonCard>
        ))}
      </div>

      {/* Story Arcs List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {[1, 2, 3].map((s) => (
          <div key={s} className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Story Card Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Skeleton width={40} height={40} borderRadius={20} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Skeleton width={160} height={16} borderRadius={4} />
                    <Skeleton width={80} height={18} borderRadius={10} />
                  </div>
                  <Skeleton width={220} height={12} borderRadius={3} />
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Skeleton width={90} height={22} borderRadius={10} />
                <Skeleton width={24} height={24} borderRadius={4} />
              </div>
            </div>

            {/* Narrative summary placeholder */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: 6,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <Skeleton width="95%" height={12} borderRadius={3} />
              <Skeleton width="75%" height={12} borderRadius={3} />
            </div>

            {/* Sequence Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflowX: 'hidden' }}>
              {[1, 2, 3, 4].map((p) => (
                <React.Fragment key={p}>
                  <Skeleton width={110} height={28} borderRadius={6} />
                  {p < 4 && <Skeleton width={16} height={10} borderRadius={2} />}
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
