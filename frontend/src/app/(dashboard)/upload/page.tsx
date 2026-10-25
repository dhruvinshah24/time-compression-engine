'use client';

import { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload as UploadIcon, FileVideo, AlertCircle, CheckCircle2,
  Clock, Cpu, Layers, Maximize2, Film, Zap, Sparkles, ArrowRight
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { API_BASE } from '@/lib/api/client';

// ── Processing profile badge colours ──────────────────────────────────────────
const PROFILE_COLOURS: Record<string, string> = {
  'Quick Test':         'text-emerald-400 bg-emerald-500/10 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]',
  'Short Clip':         'text-blue-400 bg-blue-500/10 border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.15)]',
  'Standard':           'text-purple-400 bg-purple-500/10 border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.15)]',
  'Long Recording':     'text-amber-400 bg-amber-500/10 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]',
  'Extended Recording': 'text-red-400 bg-red-500/10 border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.15)]',
  'Custom':             'text-white/40 bg-white/5 border-white/10',
};

interface UploadResult {
  video_id: string;
  job_id: string;
  filename: string;
  status: string;
  metadata: {
    duration_hms: string;
    duration_seconds: number | null;
    fps: number | null;
    frame_count: number | null;
    resolution: string;
    codec: string;
    file_size_bytes: number;
    profile: string;
    estimated_frames: number | null;
    estimated_processing_s: number | null;
    estimated_keyframes: number | null;
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatEst(s: number | null): string {
  if (s === null) return '—';
  if (s < 60) return `~${s}s`;
  return `~${Math.round(s / 60)}m`;
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [domain, setDomain] = useState('general');
  const [modelProfile, setModelProfile] = useState('balanced');
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles[0]) {
      setFile(acceptedFiles[0]);
      setUploadResult(null);
      setUploadError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'] },
    maxFiles: 1,
    disabled: uploading,
  });

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_domain', domain);
    formData.append('model_profile', modelProfile);

    try {
      const result = await new Promise<UploadResult>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setUploadProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.onabort = () => reject(new Error('Upload cancelled'));

        xhr.open('POST', `${API_BASE}/upload/`);
        xhr.send(formData);
      });

      setUploadResult(result);
      setUploading(false);
      // Auto-navigate to live pipeline processing monitor
      setTimeout(() => {
        router.push(`/processing/${result.job_id}`);
      }, 700);
    } catch (err) {
      setUploading(false);
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleCancel = () => {
    if (xhrRef.current) {
      xhrRef.current.abort();
      xhrRef.current = null;
    }
    setFile(null);
    setUploading(false);
    setUploadProgress(0);
    setUploadError(null);
    setUploadResult(null);
  };

  const handleStartProcessing = () => {
    if (uploadResult) {
      router.push(`/processing/${uploadResult.job_id}`);
    }
  };

  const domains = [
    { value: 'general',     label: 'General Video' },
    { value: 'cctv',        label: 'CCTV / Security Surveillance' },
    { value: 'sports',      label: 'Sports Analytics' },
    { value: 'medical',     label: 'Medical / Laboratory' },
    { value: 'drone',       label: 'Aerial / Drone Flight' },
    { value: 'dashcam',     label: 'Dashcam Roadway' },
    { value: 'screencast',  label: 'Screencast Telemetry' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-7 animate-slide-up">
      {/* Header */}
      <div className="pb-2 border-b border-white/5">
        <h1 className="text-2xl font-bold text-white tracking-tight">Ingest Video Stream</h1>
        <p className="text-white/40 text-xs mt-1 font-mono">
          Submit raw video footage into the 12-stage temporal analysis pipeline
        </p>
      </div>

      {/* Error banner */}
      <AnimatePresence>
        {uploadError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="flex items-start gap-3 p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-300"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-400" />
            <div className="flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider font-mono">Upload Error</p>
              <p className="text-xs mt-0.5 text-rose-300/80 font-mono">{uploadError}</p>
            </div>
            <button onClick={() => setUploadError(null)} className="text-rose-400 hover:text-white text-xs">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Metadata Success Card ────────────────────────────────────────── */}
      <AnimatePresence>
        {uploadResult && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
            className="surface-card rounded-3xl border p-7 space-y-6"
          >
            <div className="flex items-center gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                <CheckCircle2 size={22} />
              </div>
              <div>
                <p className="text-base font-bold text-white tracking-tight">Ingestion & Probing Complete</p>
                <p className="text-xs text-white/40 font-mono mt-0.5">{uploadResult.job_id}</p>
              </div>
              <div className={`ml-auto px-3.5 py-1 rounded-full border text-xs font-mono font-semibold ${
                PROFILE_COLOURS[uploadResult.metadata.profile] ?? PROFILE_COLOURS['Custom']
              }`}>
                {uploadResult.metadata.profile}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
              {[
                { icon: Clock,      label: 'Duration',         value: uploadResult.metadata.duration_hms },
                { icon: Film,       label: 'Frame Count',      value: uploadResult.metadata.estimated_frames?.toLocaleString() ?? '—' },
                { icon: Zap,        label: 'Framerate',        value: uploadResult.metadata.fps ? `${uploadResult.metadata.fps.toFixed(1)} fps` : '—' },
                { icon: Maximize2,  label: 'Resolution',       value: uploadResult.metadata.resolution },
                { icon: Cpu,        label: 'Est. Processing',  value: formatEst(uploadResult.metadata.estimated_processing_s) },
                { icon: Layers,     label: 'Video Codec',      value: uploadResult.metadata.codec },
                { icon: FileVideo,  label: 'File Size',        value: formatBytes(uploadResult.metadata.file_size_bytes) },
                { icon: Sparkles,   label: 'Keyframes',        value: uploadResult.metadata.estimated_keyframes?.toLocaleString() ?? '—' },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="surface-inset rounded-xl p-3.5 border border-white/5">
                  <div className="flex items-center gap-1.5 mb-1.5 text-white/40 text-[10px] font-mono uppercase tracking-wider">
                    <Icon size={12} className="text-indigo-400" />
                    <span>{label}</span>
                  </div>
                  <p className="text-sm font-semibold text-white font-mono truncate">{value ?? '—'}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-3 pt-2">
              <motion.button
                whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                onClick={handleStartProcessing}
                className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-600 hover:from-indigo-500 hover:to-violet-500 text-white py-3 rounded-xl font-semibold text-sm shadow-[0_0_20px_rgba(99,102,241,0.35)] transition-all"
              >
                Launch Pipeline Processing <ArrowRight size={16} />
              </motion.button>
              <button
                onClick={handleCancel}
                className="px-5 py-3 rounded-xl surface-inset border border-white/10 text-white/60 hover:text-white transition-colors text-xs font-mono"
              >
                Upload Different File
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Dropzone & Upload Form ────────────────────────────────────────── */}
      {!uploadResult && (
        <>
          {!file ? (
            <div
              {...getRootProps()}
              className={`surface-card border-2 border-dashed rounded-3xl p-16 flex flex-col items-center justify-center cursor-pointer transition-all ${
                isDragActive
                  ? 'border-indigo-500 bg-indigo-500/5 shadow-[0_0_30px_rgba(99,102,241,0.2)]'
                  : 'border-white/10 hover:border-indigo-500/50 hover:bg-white/[0.01]'
              }`}
            >
              <input {...getInputProps()} />
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-5 text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.2)]">
                <UploadIcon size={28} />
              </div>
              <h3 className="text-lg font-bold text-white mb-1.5 tracking-tight">Drop video archive here</h3>
              <p className="text-white/40 text-xs mb-5 font-mono">or click to browse local filesystem</p>
              <span className="text-[11px] font-mono px-3 py-1 rounded-full surface-inset border border-white/10 text-white/50">
                MP4 · AVI · MOV · MKV · WEBM
              </span>
            </div>
          ) : (
            <div className="surface-card rounded-3xl border p-7 space-y-6">
              {/* Selected File Card */}
              <div className="flex items-center gap-4 surface-inset p-4 rounded-2xl border border-white/5">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 flex-shrink-0">
                  <FileVideo size={22} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white truncate text-sm">{file.name}</p>
                  <p className="text-xs text-white/40 font-mono mt-0.5">{formatBytes(file.size)}</p>
                </div>
                {!uploading && (
                  <button
                    onClick={handleCancel}
                    className="text-xs text-white/40 hover:text-white px-3 py-1.5 rounded-lg surface-card border"
                  >
                    Change
                  </button>
                )}
              </div>

              {/* Upload Progress */}
              {uploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-white/50">Uploading stream to ingest buffer…</span>
                    <span className="text-indigo-400 font-bold">{uploadProgress}%</span>
                  </div>
                  <div className="h-2 w-full surface-inset rounded-full overflow-hidden border border-white/5">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                      className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full relative overflow-hidden"
                    >
                      <div className="absolute inset-0 bg-white/20 animate-pulse" />
                    </motion.div>
                  </div>
                </div>
              )}

              {/* Domain & Profile Selectors */}
              {!uploading && (
                <div className="space-y-4">
                  <div>
                    <label htmlFor="source-domain" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-2">
                      Analytical Context Domain
                    </label>
                    <select
                      id="source-domain"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      className="w-full surface-inset border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white outline-none focus:border-indigo-500 font-mono transition-colors"
                    >
                      {domains.map((d) => (
                        <option key={d.value} value={d.value} className="bg-[#090b10] text-white">
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label htmlFor="model-profile" className="block text-xs font-mono uppercase tracking-wider text-white/60 mb-2">
                      Processing Engine Profile
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: 'fast', name: 'Ultra Fast', desc: '80 FPS · Quick Ingestion' },
                        { id: 'balanced', name: 'Balanced', desc: '32 FPS · Standard Surveillance' },
                        { id: 'accuracy', name: 'Max Precision', desc: 'Deep Multi-Scale Analysis' },
                      ].map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setModelProfile(p.id)}
                          className={`p-3 rounded-xl border text-left transition-all ${
                            modelProfile === p.id
                              ? 'border-indigo-500 bg-indigo-500/15 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
                              : 'border-white/5 bg-white/[0.02] hover:border-white/10'
                          }`}
                        >
                          <div className={`text-xs font-bold ${modelProfile === p.id ? 'text-indigo-300' : 'text-white'}`}>
                            {p.name}
                          </div>
                          <div className="text-[10px] text-white/40 font-mono mt-0.5">{p.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-1">
                {!uploading ? (
                  <motion.button
                    whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                    onClick={handleUpload}
                    className="flex-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white py-3 rounded-xl font-semibold text-xs shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all"
                  >
                    Upload & Probe Stream Telemetry
                  </motion.button>
                ) : (
                  <button
                    onClick={handleCancel}
                    className="flex-1 py-3 rounded-xl surface-inset border border-white/10 text-white/50 hover:text-white transition-colors text-xs font-mono"
                  >
                    Abort Upload
                  </button>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
