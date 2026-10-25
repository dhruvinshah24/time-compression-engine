import React from 'react';
import { Skeleton, SkeletonCard } from './SkeletonElements';

export function AnalyticsSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={180} height={24} borderRadius={4} />
          <Skeleton width={320} height={13} borderRadius={3} />
        </div>
        <Skeleton width={120} height={28} borderRadius={5} />
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

      {/* Chart Section */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Skeleton width={20} height={20} borderRadius={4} />
            <Skeleton width={200} height={16} borderRadius={4} />
          </div>
          <Skeleton width={80} height={18} borderRadius={10} />
        </div>

        {/* Bar Chart Simulation */}
        <div
          style={{
            height: 220,
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            padding: '20px 10px 10px',
            gap: 12,
            borderBottom: '1px solid var(--border)',
          }}
        >
          {[45, 75, 30, 90, 60, 85, 40, 70, 95, 55, 80, 65].map((heightPct, idx) => (
            <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <Skeleton width="100%" height={`${heightPct}%`} borderRadius={4} />
              <Skeleton width={24} height={10} borderRadius={2} />
            </div>
          ))}
        </div>
      </div>

      {/* Stage Latency Table */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Skeleton width={220} height={16} borderRadius={4} />
          <Skeleton width={90} height={18} borderRadius={10} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1, 2, 3, 4, 5].map((r) => (
            <div
              key={r}
              style={{
                display: 'grid',
                gridTemplateColumns: '180px 1fr 100px',
                alignItems: 'center',
                gap: 16,
                padding: '10px 12px',
                borderRadius: 6,
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-dim)',
              }}
            >
              <Skeleton width={140} height={13} borderRadius={3} />
              <Skeleton width="100%" height={8} borderRadius={4} />
              <Skeleton width={60} height={13} borderRadius={3} style={{ justifySelf: 'end' }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
