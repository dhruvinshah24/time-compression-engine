import React from 'react';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
}

export function Skeleton({ className = '', style = {}, width, height, borderRadius }: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{
        width: width ?? '100%',
        height: height ?? '100%',
        borderRadius: borderRadius ?? 6,
        ...style,
      }}
    />
  );
}

export function SkeletonCard({
  children,
  style = {},
  className = '',
}: {
  children?: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div
      className={`card ${className}`}
      style={{
        padding: 20,
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
