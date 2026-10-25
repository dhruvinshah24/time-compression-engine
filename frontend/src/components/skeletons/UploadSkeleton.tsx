import React from 'react';
import { Skeleton } from './SkeletonElements';

export function UploadSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%', maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Skeleton width={180} height={24} borderRadius={4} />
        <Skeleton width={380} height={13} borderRadius={3} />
      </div>

      {/* Drag & Drop Card */}
      <div
        className="card"
        style={{
          padding: 48,
          border: '2px dashed var(--border)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
          backgroundColor: 'var(--bg-inset)',
          minHeight: 280,
        }}
      >
        <Skeleton width={64} height={64} borderRadius={32} />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, width: '100%' }}>
          <Skeleton width={260} height={16} borderRadius={4} />
          <Skeleton width={180} height={12} borderRadius={3} />
        </div>
        <Skeleton width={130} height={36} borderRadius={6} />
      </div>

      {/* Parameter Selectors */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
        <div className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Skeleton width={120} height={14} borderRadius={3} />
          <Skeleton width="100%" height={36} borderRadius={6} />
        </div>
        <div className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Skeleton width={140} height={14} borderRadius={3} />
          <Skeleton width="100%" height={36} borderRadius={6} />
        </div>
      </div>
    </div>
  );
}
