import React from 'react';
import { Skeleton } from './SkeletonElements';

export function SettingsSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={160} height={24} borderRadius={4} />
          <Skeleton width={340} height={13} borderRadius={3} />
        </div>
        <Skeleton width={100} height={28} borderRadius={5} />
      </div>

      {/* Filter Tabs & Search Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {[80, 90, 85, 100, 75, 80].map((w, idx) => (
            <Skeleton key={idx} width={w} height={30} borderRadius={6} />
          ))}
        </div>
        <Skeleton width={180} height={32} borderRadius={6} />
      </div>

      {/* Settings Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
          <div
            key={s}
            className="card"
            style={{
              padding: 16,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flex: 1 }}>
                <Skeleton width={32} height={32} borderRadius={6} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
                  <Skeleton width="60%" height={15} borderRadius={3} />
                  <Skeleton width="90%" height={11} borderRadius={3} />
                </div>
              </div>
              <Skeleton width={60} height={20} borderRadius={10} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 8, borderTop: '1px solid var(--border-dim)' }}>
              <Skeleton width={110} height={12} borderRadius={3} />
              <Skeleton width={70} height={14} borderRadius={4} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
