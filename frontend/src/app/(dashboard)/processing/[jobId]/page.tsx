'use client';

import { motion } from 'framer-motion';
import { PIPELINE_STAGES, ENGINE_COLORS } from '@/config/pipeline-stages';
import { EngineType } from '@/lib/types';
import { CheckCircle2, Clock, XCircle, Loader2, Play } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function ProcessingPage({ params }: { params: { jobId: string } }) {
  const [currentStageIdx, setCurrentStageIdx] = useState(3); // Mock: 4th stage running (index 3)
  
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentStageIdx(prev => prev < PIPELINE_STAGES.length - 1 ? prev + 1 : prev);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const getStageStatus = (index: number) => {
    if (index < currentStageIdx) return 'completed';
    if (index === currentStageIdx) return 'running';
    return 'pending';
  };

  const engineGroups = PIPELINE_STAGES.reduce((acc, stage) => {
    if (!acc[stage.engine]) acc[stage.engine] = [];
    acc[stage.engine].push(stage);
    return acc;
  }, {} as Record<EngineType, typeof PIPELINE_STAGES>);

  return (
    <div className="h-full flex flex-col animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">cam_front_door_04.mp4</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
              JOB-{params.jobId}
            </span>
          </div>
          <p className="text-sm text-muted">Processing pipeline active. Estimating 1m 45s remaining.</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-mono text-white mb-1">
            {Math.round((currentStageIdx / PIPELINE_STAGES.length) * 100)}%
          </div>
          <div className="text-xs text-muted">Overall Progress</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="col-span-2 overflow-y-auto pr-2 space-y-8">
          {(Object.keys(engineGroups) as EngineType[]).map((engine) => (
            <div key={engine} className="space-y-4">
              <div className="flex items-center gap-3 border-b border-border pb-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ENGINE_COLORS[engine] }}></div>
                <h2 className="text-lg font-medium text-white">{engine}</h2>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                {engineGroups[engine].map((stage) => {
                  const status = getStageStatus(stage.number - 1);
                  const isRunning = status === 'running';
                  const isDone = status === 'completed';
                  
                  return (
                    <motion.div
                      key={stage.id}
                      layout
                      className={`relative overflow-hidden rounded-xl border p-4 ${
                        isRunning ? 'border-accent bg-accent/5 stage-active' :
                        isDone ? 'border-success/30 bg-success/5' :
                        'border-border bg-surface opacity-60'
                      }`}
                    >
                      {isRunning && (
                        <div className="absolute top-0 left-0 h-1 bg-accent w-full overflow-hidden">
                          <motion.div 
                            className="h-full bg-white/50 w-1/3"
                            animate={{ x: ['-100%', '300%'] }}
                            transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                          />
                        </div>
                      )}
                      
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                            isRunning ? 'bg-accent text-white' : 'bg-background text-muted border border-border'
                          }`}>
                            {stage.number.toString().padStart(2, '0')}
                          </span>
                          <span className="font-medium text-white">{stage.name}</span>
                        </div>
                        {isRunning && <Loader2 className="w-4 h-4 text-accent animate-spin" />}
                        {isDone && <CheckCircle2 className="w-4 h-4 text-success" />}
                        {status === 'pending' && <Clock className="w-4 h-4 text-muted" />}
                      </div>
                      
                      <p className="text-xs text-muted mb-4">{stage.description}</p>
                      
                      {isDone && (
                        <div className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded inline-block">
                          Completed in {Math.floor(Math.random() * 20 + 5)}s
                        </div>
                      )}
                      {isRunning && (
                        <div className="text-xs font-mono text-accent bg-accent/10 px-2 py-1 rounded inline-block">
                          Processing...
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="col-span-1 h-full flex flex-col">
          <div className="glass rounded-xl border border-border flex flex-col h-full overflow-hidden">
            <div className="p-4 border-b border-border bg-surface flex items-center justify-between">
              <h3 className="font-medium text-white flex items-center gap-2">
                <Play className="w-4 h-4" /> Live Log Output
              </h3>
              <div className="flex gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
              </div>
            </div>
            <div className="flex-1 p-4 bg-[#050505] overflow-y-auto font-mono text-xs text-muted space-y-1.5">
              <div>[08:34:12] Initializing job {params.jobId}</div>
              <div>[08:34:12] Stage s01_upload: completed in 2,340ms</div>
              <div>[08:34:12] Stage s02_extract: started</div>
              <div>[08:34:42] Extracted 14,400 frames at skip_rate=5</div>
              <div>[08:34:43] Stage s02_extract: completed in 31,204ms</div>
              <div>[08:34:43] Stage s03_scene_detect: started</div>
              <div>[08:35:01] Detected 23 scene changes</div>
              <div>[08:35:01] Stage s03_scene_detect: completed in 18,392ms</div>
              {currentStageIdx >= 3 && <div className="text-white">[08:35:01] Stage s04_object_detect: started</div>}
              {currentStageIdx >= 3 && <div className="text-accent animate-pulse">Processing frame 1240/14400...</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
