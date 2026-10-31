'use client';

import { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload as UploadIcon, FileVideo, AlertCircle, CheckCircle2,
  Clock, Cpu, Layers, Maximize2, Film, Zap, ArrowRight,
  ChevronRight, HardDrive, ShieldCheck, Check, Sparkles, X
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { API_BASE } from '@/lib/api/client';

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

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [domain, setDomain] = useState('cctv_indoor');
  const [modelProfile, setModelProfile] = useState<'accuracy' | 'balanced' | 'fast'>('balanced');
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

  const handleCancel = () => {
    if (xhrRef.current) {
      xhrRef.current.abort();
    }
    setFile(null);
    setUploading(false);
    setUploadProgress(0);
    setUploadError(null);
    setUploadResult(null);
  };

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
            try {
              resolve(JSON.parse(xhr.responseText));
            } catch {
              reject(new Error('Invalid response from server'));
            }
          } else {
            let msg = `Upload failed with HTTP ${xhr.status}`;
            try {
              const err = JSON.parse(xhr.responseText);
              if (err.detail) msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
            } catch {}
            reject(new Error(msg));
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.onabort = () => reject(new Error('Upload aborted by user'));
        xhr.open('POST', `${API_BASE}/upload/`);
        xhr.send(formData);
      });

      setUploadResult(result);
      setUploading(false);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
      setUploading(false);
    }
  };

  // Determine current active step in guided flow
  const currentStep = uploadResult ? 4 : uploading ? 3 : file ? 2 : 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 960, margin: '0 auto', width: '100%' }}>
      {/* ── Header & Breadcrumb ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6
          }}>
            <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Dashboard</Link>
            <span>/</span>
            <span style={{ color: 'var(--text-secondary)' }}>Ingestion Workstation</span>
          </div>

          <h1 style={{
            fontSize: 22, fontWeight: 700, color: 'var(--text-primary)',
            letterSpacing: '-0.02em', margin: 0
          }}>
            Video Ingestion & Stream Processing
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2, marginBottom: 0 }}>
            Upload raw surveillance footage for temporal extraction, actor re-identification, and causal event generation.
          </p>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px', borderRadius: 6,
          backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)'
        }}>
          <ShieldCheck size={14} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            Pipeline v1.1 Ingestion Ready
          </span>
        </div>
      </div>

      {/* ── 4-Stage Guided Stepper ───────────────────────────────────────── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
        backgroundColor: 'var(--bg-panel)', padding: 6, borderRadius: 8,
        border: '1px solid var(--border)'
      }}>
        {[
          { step: 1, title: 'Select Footage', desc: 'Raw surveillance archive' },
          { step: 2, title: 'Camera Domain', desc: 'Indoor / Outdoor / Retail' },
          { step: 3, title: 'Inference Engine', desc: 'YOLO11 model profile' },
          { step: 4, title: 'Pipeline Dispatch', desc: '12-stage execution' },
        ].map((s) => {
          const isActive = currentStep === s.step;
          const isDone = currentStep > s.step;
          return (
            <div
              key={s.step}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderRadius: 6,
                backgroundColor: isActive ? 'var(--bg-raised)' : 'transparent',
                border: `1px solid ${isActive ? 'var(--accent-dim)' : 'transparent'}`,
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{
                width: 22, height: 22, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
                backgroundColor: isDone ? 'var(--accent)' : isActive ? 'var(--accent-bg)' : 'var(--bg-inset)',
                color: isDone ? '#0F1915' : isActive ? 'var(--accent)' : 'var(--text-muted)',
                border: `1px solid ${isDone ? 'var(--accent)' : isActive ? 'var(--accent)' : 'var(--border)'}`,
                flexShrink: 0
              }}>
                {isDone ? <Check size={12} strokeWidth={3} /> : s.step}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{
                  fontSize: 12, fontWeight: 600,
                  color: isActive ? 'var(--text-primary)' : isDone ? 'var(--text-secondary)' : 'var(--text-muted)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>
                  {s.title}
                </div>
                <div style={{
                  fontSize: 10, color: 'var(--text-muted)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>
                  {s.desc}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Ingestion Form Card ─────────────────────────────────────────── */}
      <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 22 }}>
        {/* Step 1: File Dropzone */}
        {!file && (
          <div
            {...getRootProps()}
            style={{
              border: `2px dashed ${isDragActive ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 8,
              backgroundColor: isDragActive ? 'var(--accent-bg)' : 'var(--bg-inset)',
              padding: '56px 24px',
              textAlign: 'center',
              cursor: uploading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 14
            }}
          >
            <input {...getInputProps()} />

            <div style={{
              width: 52, height: 52, borderRadius: '50%',
              backgroundColor: 'var(--bg-raised)', border: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--accent)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
            }}>
              <UploadIcon size={24} />
            </div>

            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                Drag & drop surveillance footage here, or browse files
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                Supports MP4, AVI, MOV, MKV, and WebM containers up to 4GB.
              </div>
            </div>

            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 4,
              backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-dim)',
              fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)'
            }}>
              <Zap size={11} style={{ color: 'var(--accent)' }} />
              <span>GPU Accelerated Keyframe Ingestion</span>
            </div>
          </div>
        )}

        {/* Selected File Banner */}
        {file && !uploadResult && (
          <div className="card-inset" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 6,
                backgroundColor: 'var(--accent-bg)', border: '1px solid var(--accent-dim)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--accent)', flexShrink: 0
              }}>
                <FileVideo size={22} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{file.name}</div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{formatBytes(file.size)}</span>
                  <span>•</span>
                  <span>{file.type || 'video/mp4'}</span>
                  <span>•</span>
                  <span style={{ color: 'var(--accent)' }}>Ready for dispatch</span>
                </div>
              </div>
            </div>

            {!uploading && (
              <button
                onClick={handleCancel}
                className="btn btn-secondary"
                style={{ fontSize: 11, padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <X size={12} />
                <span>Change File</span>
              </button>
            )}
          </div>
        )}

        {/* Step 2: Camera Environment Profile */}
        {!uploadResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Surveillance Environment Profile
              </label>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                Calibrates motion sensitivity & background thresholds
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {[
                { id: 'cctv_indoor', label: 'CCTV Indoor', desc: 'Offices, research labs & secure hallways' },
                { id: 'cctv_outdoor', label: 'CCTV Outdoor', desc: 'Perimeters, loading bays & access gates' },
                { id: 'retail', label: 'Retail & POS', desc: 'Point of sale registers & customer aisles' },
                { id: 'general', label: 'General Motion', desc: 'Unconstrained wide-angle field of view' },
              ].map((d) => {
                const active = domain === d.id;
                return (
                  <div
                    key={d.id}
                    onClick={() => !uploading && setDomain(d.id)}
                    style={{
                      padding: '12px 14px', borderRadius: 6,
                      backgroundColor: active ? 'var(--accent-bg)' : 'var(--bg-inset)',
                      border: `1px solid ${active ? 'var(--accent-dim)' : 'var(--border)'}`,
                      cursor: uploading ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text-primary)' }}>
                        {d.label}
                      </span>
                      {active && <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent)' }} />}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                      {d.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 3: Model & Inference Engine Profile */}
        {!uploadResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Inference & Model Profile
              </label>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                Selects neural weights for detection & tracking
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
              {[
                { id: 'accuracy', label: 'Accuracy Profile', spec: 'YOLO11x @ 32 FPS', desc: 'Deep forensic scrutiny, keypoint pose analysis, high ReID fidelity' },
                { id: 'balanced', label: 'Balanced Profile', spec: 'YOLO11l @ 32 FPS', desc: 'Standard security balance of precision and real-time processing' },
                { id: 'fast', label: 'Fast Triage Profile', spec: 'YOLO11n @ 80 FPS', desc: 'High-speed screening, rapid triage, and macro event detection' },
              ].map((m) => {
                const active = modelProfile === m.id;
                return (
                  <div
                    key={m.id}
                    onClick={() => !uploading && setModelProfile(m.id as any)}
                    style={{
                      padding: '12px 14px', borderRadius: 6,
                      backgroundColor: active ? 'var(--accent-bg)' : 'var(--bg-inset)',
                      border: `1px solid ${active ? 'var(--accent-dim)' : 'var(--border)'}`,
                      cursor: uploading ? 'not-allowed' : 'pointer',
                      transition: 'all 0.15s'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text-primary)' }}>
                        {m.label}
                      </span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: active ? 'var(--accent)' : 'var(--text-muted)' }}>
                        {m.spec}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                      {m.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Upload Streaming Progress Bar */}
        {uploading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px', borderRadius: 6, backgroundColor: 'var(--bg-inset)', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 1.2s infinite' }} />
                Streaming video chunks to pipeline engine...
              </span>
              <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{uploadProgress}%</span>
            </div>
            <div className="progress-track" style={{ height: 6 }}>
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
              <button
                onClick={handleCancel}
                className="btn btn-secondary"
                style={{ fontSize: 11, padding: '4px 10px' }}
              >
                Abort Upload
              </button>
            </div>
          </div>
        )}

        {/* Upload Error Banner */}
        {uploadError && (
          <div className="card-inset" style={{ padding: 14, border: '1px solid var(--danger)', display: 'flex', alignItems: 'center', gap: 12 }}>
            <AlertCircle size={18} style={{ color: 'var(--danger)', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--danger)' }}>Upload Failed</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{uploadError}</div>
            </div>
          </div>
        )}

        {/* Upload Success & Result Details */}
        {uploadResult && (
          <div className="card-inset" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, border: '1px solid var(--accent-dim)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                backgroundColor: 'var(--accent-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--accent)'
              }}>
                <CheckCircle2 size={18} />
              </div>
              <div>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                  Footage Successfully Ingested & Job Dispatched
                </span>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
                  Video ID: {uploadResult.video_id} • Job ID: {uploadResult.job_id}
                </p>
              </div>
            </div>

            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 12, padding: 14, borderRadius: 6, backgroundColor: 'var(--bg-panel)',
              fontSize: 11, fontFamily: 'var(--font-mono)', border: '1px solid var(--border-dim)'
            }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Duration:</span>{' '}
                <strong style={{ color: 'var(--text-primary)' }}>{uploadResult.metadata?.duration_hms || '00:01:00'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Resolution:</span>{' '}
                <strong style={{ color: 'var(--text-primary)' }}>{uploadResult.metadata?.resolution || '1920x1080'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Profile:</span>{' '}
                <strong style={{ color: 'var(--accent)' }}>{uploadResult.metadata?.profile || modelProfile}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Framerate:</span>{' '}
                <strong style={{ color: 'var(--text-primary)' }}>{uploadResult.metadata?.fps ? `${uploadResult.metadata.fps.toFixed(1)} fps` : '30.0 fps'}</strong>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
              <button
                onClick={() => router.push(`/processing/${uploadResult.job_id}`)}
                className="btn btn-primary"
                style={{ fontSize: 12, padding: '9px 18px', fontWeight: 700 }}
              >
                <span>Track Live Pipeline</span>
                <ArrowRight size={14} />
              </button>

              <button
                onClick={() => router.push(`/timeline/${uploadResult.video_id}`)}
                className="btn btn-secondary"
                style={{ fontSize: 12, padding: '9px 18px' }}
              >
                <span>Direct to Forensic Timeline</span>
              </button>

              <button
                onClick={handleCancel}
                className="btn btn-ghost"
                style={{ fontSize: 12, padding: '9px 18px' }}
              >
                <span>Ingest Another Stream</span>
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Dispatch Action Button */}
        {!uploadResult && (
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="btn btn-primary"
            style={{
              padding: '13px 20px',
              fontSize: 13,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              opacity: !file || uploading ? 0.6 : 1,
              cursor: !file || uploading ? 'not-allowed' : 'pointer'
            }}
          >
            <Zap size={15} />
            <span>{uploading ? `Streaming to Engine (${uploadProgress}%)...` : 'Dispatch to 12-Stage Pipeline Engine'}</span>
          </button>
        )}
      </div>
    </div>
  );
}
