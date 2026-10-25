import React from 'react';
import { Skeleton } from './SkeletonElements';

export function EventsSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      {/* Breadcrumb & Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Skeleton width={140} height={12} borderRadius={3} />
          <Skeleton width={200} height={24} borderRadius={4} />
          <Skeleton width={380} height={13} borderRadius={3} />
        </div>

        {/* Global Controls & Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Skeleton width={180} height={32} borderRadius={6} />
          <Skeleton width={140} height={32} borderRadius={6} />
          <Skeleton width={110} height={32} borderRadius={6} />
        </div>
      </div>

      {/* Stream Group Cards */}
      {[1, 2].map((s) => (
        <div key={s} className="card" style={{ overflow: 'hidden' }}>
          {/* Stream Header */}
          <div
            style={{
              padding: '12px 18px',
              backgroundColor: 'var(--bg-raised)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Skeleton width={32} height={32} borderRadius={6} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Skeleton width={180} height={16} borderRadius={4} />
                  <Skeleton width={80} height={16} borderRadius={10} />
                </div>
                <Skeleton width={130} height={11} borderRadius={3} />
              </div>
            </div>
            <Skeleton width={160} height={28} borderRadius={6} />
          </div>

          {/* Event Items List */}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {[1, 2, 3, 4].map((idx) => (
              <div
                key={idx}
                style={{
                  padding: '13px 18px',
                  display: 'grid',
                  gridTemplateColumns: '120px 1fr 140px 120px 100px',
                  alignItems: 'center',
                  gap: 16,
                  borderBottom: idx === 4 ? 'none' : '1px solid var(--border-dim)',
                  backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(25, 29, 32, 0.4)',
                }}
              >
                {/* Timecode Badge */}
                <Skeleton width={75} height={20} borderRadius={10} />

                {/* Event Title & Involves */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <Skeleton width="45%" height={14} borderRadius={3} />
                  <Skeleton width="75%" height={11} borderRadius={3} />
                </div>

                {/* Actor Badge */}
                <Skeleton width={85} height={22} borderRadius={12} />

                {/* Confidence */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Skeleton width={50} height={6} borderRadius={3} />
                  <Skeleton width={32} height={12} borderRadius={3} />
                </div>

                {/* Action button */}
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Skeleton width={68} height={24} borderRadius={5} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
