'use client';

import { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion } from 'framer-motion';
import { Upload as UploadIcon, FileVideo, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [domain, setDomain] = useState('cctv');
  const [uploadError, setUploadError] = useState<string | null>(null);
  // Ref keeps the interval ID accessible to the Cancel handler so it can be
  // cleared even if Cancel is clicked while an upload is in progress.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles[0]) setFile(acceptedFiles[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'] },
    maxFiles: 1
  });

  const handleUpload = () => {
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    let p = 0;
    try {
      intervalRef.current = setInterval(() => {
        p += 5;
        setProgress(p);
        if (p >= 100) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setTimeout(() => router.push('/processing/demo'), 500);
        }
      }, 100);
    } catch (err) {
      setUploading(false);
      setUploadError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    }
  };

  const handleCancel = () => {
    // Clear any in-flight fake upload interval before resetting state.
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setFile(null);
    setUploading(false);
    setProgress(0);
    setUploadError(null);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-slide-up">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Upload Video for Analysis</h1>
        <p className="text-muted mt-2">Submit raw footage to the Time Compression Engine.</p>
      </div>

      {uploadError && (
        <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-300">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium">Upload failed</p>
            <p className="text-xs mt-0.5 text-red-400">{uploadError}</p>
          </div>
          <button onClick={() => setUploadError(null)} className="text-red-400 hover:text-red-300 text-xs">✕</button>
        </div>
      )}

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
          <div className="flex gap-2">
            {['MP4', 'AVI', 'MOV', 'MKV', 'WEBM'].map(ext => (
              <span key={ext} className="text-xs font-mono bg-background border border-border px-2 py-1 rounded text-muted">
                {ext}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-6">
          <div className="glass rounded-xl border border-border p-6 flex items-start gap-6">
            <div className="w-32 h-32 bg-background rounded-lg border border-border flex items-center justify-center">
              <FileVideo className="w-12 h-12 text-muted" />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-white mb-4">{file.name}</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-surface p-3 rounded-lg border border-border/50">
                  <div className="text-xs text-muted mb-1">File Size</div>
                  <div className="font-mono text-white">{(file.size / (1024 * 1024)).toFixed(2)} MB</div>
                </div>
                <div className="bg-surface p-3 rounded-lg border border-border/50">
                  <div className="text-xs text-muted mb-1">Duration</div>
                <div className="font-mono text-white">~45:00</div>
                </div>
                <div className="bg-surface p-3 rounded-lg border border-border/50">
                  <div className="text-xs text-muted mb-1">Est. Processing</div>
                <div className="font-mono text-white text-muted">Estimated after upload</div>
                </div>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl border border-border p-6">
            <label className="block text-sm font-medium text-white mb-2">Source Domain</label>
            <select 
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-white outline-none focus:border-accent transition-colors"
            >
              <option value="cctv">CCTV / Security</option>
              <option value="dashcam">Dashcam</option>
              <option value="drone">Drone Footage</option>
              <option value="wildlife">Wildlife Camera</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex gap-3 text-blue-200">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">Region of Interest selection will be available in Phase 2. Currently monitoring full frame.</p>
          </div>

          {uploading ? (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-white font-medium">Uploading & Initializing...</span>
                <span className="text-accent font-mono">{progress}%</span>
              </div>
              <div className="h-3 bg-surface rounded-full overflow-hidden">
                <div 
                  className="h-full bg-accent transition-all duration-300 ease-out relative"
                  style={{ width: `${progress}%` }}
                >
                  <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex justify-end gap-4">
              <button 
                onClick={handleCancel}
                className="px-6 py-2.5 rounded-lg border border-border text-white hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleUpload}
                className="px-6 py-2.5 rounded-lg bg-accent hover:bg-accent-hover text-white font-medium glow-blue transition-colors flex items-center gap-2"
              >
                Start Analysis <UploadIcon className="w-4 h-4" />
              </button>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
