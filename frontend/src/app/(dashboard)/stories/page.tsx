'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import {
  GitFork, Film, Search, ChevronRight, ArrowRight,
  Loader2, CheckCircle2, Clock, Users, ShieldCheck
} from 'lucide-react';
import { api } from '@/lib/api/client';

export default function StoriesIndexPage() {
  const [videos, setVideos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.videos.list()
      .then((data) => {
        if (mounted) {
          setVideos(Array.isArray(data) ? data : []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Failed to load video stories');
          setLoading(false);
        }
      });
    return () => { mounted = false; };
  }, []);

  const filteredVideos = useMemo(() => {
    if (!search.trim()) return videos;
    const q = search.toLowerCase();
    return videos.filter(
      (v) =>
        v.id?.toLowerCase().includes(q) ||
        v.filename?.toLowerCase().includes(q) ||
        v.source_domain?.toLowerCase().includes(q)
    );
  }, [videos, search]);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border)] pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-muted)] mb-1">
            <Link href="/" className="hover:text-[var(--accent)] text-[var(--text-muted)] no-underline">Dashboard</Link>
            <span>/</span>
            <span className="text-[var(--text-secondary)]">Narrative Stories</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight m-0">
            Story Arcs & Causal Chains
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-2xl leading-relaxed">
            Select a processed recording to inspect structured actor narratives, causal story chains, and scene chronologies.
          </p>
        </div>

        {/* Search */}
        <div className="relative min-w-[240px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
          <input
            type="text"
            id="stories-search-input"
            name="stories-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search recordings or IDs..."
            className="w-full bg-[var(--bg-inset)] border border-[var(--border)] rounded-md pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] font-mono"
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-[var(--text-muted)]">
          <Loader2 size={24} className="animate-spin text-[var(--accent)]" />
          <span className="text-xs font-mono">Loading story arc recordings...</span>
        </div>
      ) : error ? (
        <div className="card p-6 border border-red-500/30 text-center">
          <p className="text-xs text-red-400 font-mono">{error}</p>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="card p-12 text-center flex flex-col items-center justify-center gap-3">
          <GitFork size={32} className="text-[var(--text-muted)] opacity-40" />
          <p className="text-sm font-semibold text-[var(--text-secondary)]">No video recordings found</p>
          <p className="text-xs text-[var(--text-muted)] max-w-md">
            {search ? 'No recordings matched your search query.' : 'No processed videos available for narrative extraction.'}
          </p>
          <Link href="/upload" className="btn btn-primary text-xs mt-2 no-underline">
            Upload Video
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredVideos.map((video) => {
            const durationHms = video.metadata?.duration_hms || (video.metadata?.duration_seconds ? `${Math.round(video.metadata.duration_seconds)}s` : 'Unknown');

            return (
              <div
                key={video.id}
                className="card border border-[var(--border)] hover:border-[var(--accent-dim)] rounded-lg p-4 flex flex-col justify-between gap-4 transition-all group"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-inset)] border border-[var(--border-dim)] text-[var(--text-secondary)]">
                      <GitFork size={11} className="text-[var(--accent)]" />
                      Causal Graph
                    </span>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle2 size={10} />
                      Story Chains
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors truncate m-0 mb-1" title={video.filename}>
                    {video.filename || video.id}
                  </h3>
                  <div className="text-[11px] font-mono text-[var(--text-muted)] truncate mb-3">
                    {video.id}
                  </div>

                  <div className="flex items-center gap-4 bg-[var(--bg-inset)] p-2.5 rounded border border-[var(--border-dim)] text-xs font-mono text-[var(--text-secondary)]">
                    <div className="flex items-center gap-1.5">
                      <Clock size={12} className="text-[var(--text-muted)]" />
                      <span>{durationHms}</span>
                    </div>
                    <div className="text-[var(--border)]">·</div>
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck size={12} className="text-[var(--accent)]" />
                      <span>S09 Formed</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-[var(--border-dim)]">
                  <Link
                    href={`/stories/${video.id}`}
                    className="w-full btn btn-primary text-xs py-2 px-3 justify-center gap-1.5 no-underline flex items-center font-medium"
                  >
                    <GitFork size={13} />
                    <span>View Story Arcs</span>
                    <ArrowRight size={12} className="opacity-70 group-hover:translate-x-0.5 transition-transform" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

