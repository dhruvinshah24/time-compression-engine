import React from 'react';
import { Skeleton, SkeletonCard } from './SkeletonElements';

export function DashboardSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, width: '100%' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={180} height={24} borderRadius={4} />
          <Skeleton width={260} height={14} borderRadius={4} />
        </div>
        <Skeleton width={120} height={28} borderRadius={5} />
      </div>

      {/* 4 Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '70%' }}>
                <Skeleton width="60%" height={12} borderRadius={3} />
                <Skeleton width="85%" height={26} borderRadius={4} />
              </div>
              <Skeleton width={32} height={32} borderRadius={6} />
            </div>
          </SkeletonCard>
        ))}
      </div>

      {/* 2-Column Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 16 }}>
        {/* Left: Processing / Active Jobs */}
        <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Skeleton width={20} height={20} borderRadius={4} />
              <Skeleton width={140} height={16} borderRadius={4} />
            </div>
            <Skeleton width={60} height={18} borderRadius={12} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2, 3].map((j) => (
              <div
                key={j}
                style={{
                  padding: 14,
                  borderRadius: 6,
                  border: '1px solid var(--border-dim)',
                  backgroundColor: 'var(--bg-inset)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Skeleton width={24} height={24} borderRadius={4} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Skeleton width={160} height={14} borderRadius={3} />
                      <Skeleton width={90} height={11} borderRadius={3} />
                    </div>
                  </div>
                  <Skeleton width={75} height={20} borderRadius={10} />
                </div>
                <Skeleton width="100%" height={6} borderRadius={3} />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Skeleton width={120} height={11} borderRadius={3} />
                  <Skeleton width={40} height={11} borderRadius={3} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Recent Scene Events */}
        <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Skeleton width={20} height={20} borderRadius={4} />
              <Skeleton width={150} height={16} borderRadius={4} />
            </div>
            <Skeleton width={50} height={18} borderRadius={12} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1, 2, 3, 4, 5].map((e) => (
              <div
                key={e}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: 6,
                  backgroundColor: 'var(--bg-inset)',
                  border: '1px solid var(--border-dim)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Skeleton width={45} height={18} borderRadius={4} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <Skeleton width={130} height={13} borderRadius={3} />
                    <Skeleton width={70} height={10} borderRadius={3} />
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Skeleton width={55} height={18} borderRadius={10} />
                  <Skeleton width={32} height={12} borderRadius={3} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
