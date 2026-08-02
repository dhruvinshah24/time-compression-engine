'use client';

import { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload as UploadIcon, FileVideo, AlertCircle, CheckCircle2,
  Clock, Cpu, Layers, Maximize2, Film, Zap
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';

// ── Processing profile badge colours ──────────────────────────────────────────
const PROFILE_COLOURS: Record<string, string> = {
  'Quick Test':         'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  'Short Clip':         'text-blue-400 bg-blue-400/10 border-blue-400/20',
  'Standard':           'text-purple-400 bg-purple-400/10 border-purple-400/20',
  'Long Recording':     'text-amber-400 bg-amber-400/10 border-amber-400/20',
  'Extended Recording': 'text-red-400 bg-red-400/10 border-red-400/20',
  'Custom':             'text-muted bg-surface border-border',
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

    // Use XHR for real upload progress tracking
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_domain', domain);

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

        xhr.open('POST', `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'}/upload/`);
        xhr.send(formData);
      });

      setUploadResult(result);
      setUploading(false);
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
    { value: 'general',     label: 'General' },
    { value: 'cctv',        label: 'CCTV / Surveillance' },
    { value: 'sports',      label: 'Sports' },
    { value: 'medical',     label: 'Medical / Lab' },
    { value: 'drone',       label: 'Drone / Aerial' },
    { value: 'dashcam',     label: 'Dashcam' },
    { value: 'screencast',  label: 'Screencast / Tutorial' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-slide-up">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Upload Video for Analysis</h1>
        <p className="text-muted mt-2">Submit footage to the Time Compression Engine pipeline.</p>
      </div>

      {/* Error banner */}
      <AnimatePresence>
        {uploadError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-300"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium">Upload failed</p>
              <p className="text-xs mt-0.5 text-red-400 font-mono">{uploadError}</p>
            </div>
            <button onClick={() => setUploadError(null)} className="text-red-400 hover:text-red-300 text-xs">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Success: metadata card ──────────────────────────────────────── */}
      <AnimatePresence>
        {uploadResult && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
            className="glass-strong rounded-2xl border border-border p-6 space-y-5"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-400/10 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-white font-semibold">Upload successful</p>
                <p className="text-xs text-muted font-mono">{uploadResult.job_id}</p>
              </div>
              <div className={`ml-auto px-3 py-1 rounded-full border text-xs font-medium ${
                PROFILE_COLOURS[uploadResult.metadata.profile] ?? PROFILE_COLOURS['Custom']
              }`}>
                {uploadResult.metadata.profile}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {[
                { icon: FileVideo,  label: 'Filename',         value: uploadResult.filename },
                { icon: Clock,      label: 'Duration',         value: uploadResult.metadata.duration_hms },
                { icon: Film,       label: 'Frames',           value: uploadResult.metadata.estimated_frames?.toLocaleString() ?? '—' },
                { icon: Zap,        label: 'FPS',              value: uploadResult.metadata.fps?.toFixed(2) ?? '—' },
                { icon: Maximize2,  label: 'Resolution',       value: uploadResult.metadata.resolution },
                { icon: Cpu,        label: 'Est. Processing',  value: formatEst(uploadResult.metadata.estimated_processing_s) },
                { icon: Layers,     label: 'Codec',            value: uploadResult.metadata.codec },
                { icon: FileVideo,  label: 'File Size',        value: formatBytes(uploadResult.metadata.file_size_bytes) },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="bg-surface rounded-lg border border-border px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="w-3.5 h-3.5 text-muted" />
                    <span className="text-xs text-muted">{label}</span>
                  </div>
                  <p className="text-sm font-medium text-white truncate">{value ?? '—'}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-3 pt-2">
              <motion.button
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                onClick={handleStartProcessing}
                className="flex-1 bg-accent hover:bg-accent-hover text-white py-3 rounded-lg font-semibold transition-colors glow-blue"
              >
                Start Processing →
              </motion.button>
              <button
                onClick={handleCancel}
                className="px-6 py-3 rounded-lg border border-border text-muted hover:text-white hover:bg-white/5 transition-colors text-sm"
              >
                Upload Another
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Upload area (hidden once result arrives) ───────────────────── */}
      {!uploadResult && (
        <>
          {!file ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-2xl p-20 flex flex-col items-center justify-center cursor-pointer transition-all ${
                isDragActive ? 'border-accent bg-accent/5 glow-blue' : 'border-border hover:border-accent/50 bg-surface'
              }`}
            >
              <input {...getInputProps()} />
              <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-6">
                <UploadIcon className="w-8 h-8 text-accent" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Drag & drop your video here</h3>
              <p className="text-muted mb-6">or click to browse from your computer</p>
              <p className="text-xs text-muted">Supports MP4, AVI, MOV, MKV, WebM · Any length</p>
            </div>
          ) : (
            <div className="glass rounded-2xl border border-border p-8 space-y-6">
              {/* File info */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-accent/10 flex items-center justify-center flex-shrink-0">
                  <FileVideo className="w-7 h-7 text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white truncate">{file.name}</p>
                  <p className="text-sm text-muted">{formatBytes(file.size)}</p>
                </div>
                {!uploading && (
                  <button onClick={handleCancel} className="text-muted hover:text-white text-sm">Remove</button>
                )}
              </div>

              {/* Progress bar */}
              {uploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Uploading…</span>
                    <span className="text-white font-mono">{uploadProgress}%</span>
                  </div>
                  <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                      className="h-full bg-accent rounded-full relative overflow-hidden"
                    >
                      <div className="absolute inset-0 bg-white/20 animate-pulse" />
                    </motion.div>
                  </div>
                </div>
              )}

              {/* Domain selector */}
              {!uploading && (
                <div>
                  <label htmlFor="source-domain" className="block text-sm font-medium text-white mb-2">
                    Source Domain
                  </label>
                  <select
                    id="source-domain"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-white outline-none focus:border-accent transition-colors"
                  >
                    {domains.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Upload / Cancel */}
              <div className="flex gap-3">
                {!uploading ? (
                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                    onClick={handleUpload}
                    className="flex-1 bg-accent hover:bg-accent-hover text-white py-3 rounded-lg font-semibold transition-colors glow-blue"
                  >
                    Upload & Probe Metadata
                  </motion.button>
                ) : (
                  <button
                    onClick={handleCancel}
                    className="flex-1 py-3 rounded-lg border border-border text-muted hover:text-white hover:bg-white/5 transition-colors"
                  >
                    Cancel
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
