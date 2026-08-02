import { EngineType } from '@/lib/types';

export interface PipelineStageConfig {
  id: string;
  number: number;
  name: string;
  description: string;
  engine: EngineType;
  icon: string; // Lucide icon name
  estimatedDurationSeconds: number;
  phase: number; // Which project phase implements this
}

export const PIPELINE_STAGES: PipelineStageConfig[] = [
  { id: 's01_upload', number: 1, name: 'Upload & Validate', description: 'Video received and integrity verified', engine: 'Perception Engine', icon: 'Upload', estimatedDurationSeconds: 5, phase: 1 },
  { id: 's02_extract', number: 2, name: 'Frame Extraction', description: 'Keyframes extracted at configured skip rate', engine: 'Perception Engine', icon: 'Film', estimatedDurationSeconds: 30, phase: 2 },
  { id: 's03_scene_detect', number: 3, name: 'Scene Change Detection', description: 'Identifying significant visual transitions', engine: 'Perception Engine', icon: 'Layers', estimatedDurationSeconds: 20, phase: 3 },
  { id: 's04_object_detect', number: 4, name: 'Object Detection', description: 'Detecting objects in each keyframe', engine: 'Perception Engine', icon: 'ScanSearch', estimatedDurationSeconds: 60, phase: 5 },
  { id: 's05_track', number: 5, name: 'Object Tracking', description: 'Tracking object identities across frames', engine: 'Perception Engine', icon: 'Route', estimatedDurationSeconds: 40, phase: 6 },
  { id: 's06_motion_analyze', number: 6, name: 'Motion Analysis', description: 'Computing optical flow and motion vectors', engine: 'Perception Engine', icon: 'Activity', estimatedDurationSeconds: 35, phase: 7 },
  { id: 's07_event_understand', number: 7, name: 'Event Understanding', description: 'Semantic reasoning over detected patterns', engine: 'Semantic Intelligence Engine', icon: 'Brain', estimatedDurationSeconds: 25, phase: 8 },
  { id: 's08_confidence_fuse', number: 8, name: 'Confidence Fusion', description: 'Combining multi-signal confidence scores', engine: 'Semantic Intelligence Engine', icon: 'GitMerge', estimatedDurationSeconds: 10, phase: 8 },
  { id: 's09_story_build', number: 9, name: 'Story Preservation', description: 'Building narrative-coherent event chains', engine: 'Temporal Intelligence Engine', icon: 'BookOpen', estimatedDurationSeconds: 15, phase: 9 },
  { id: 's10_rank', number: 10, name: 'Importance Ranking', description: 'Scoring events by significance', engine: 'Temporal Intelligence Engine', icon: 'BarChart3', estimatedDurationSeconds: 8, phase: 9 },
  { id: 's11_summarize', number: 11, name: 'Summary Generation', description: 'Generating AI text summary and timeline', engine: 'Temporal Intelligence Engine', icon: 'FileText', estimatedDurationSeconds: 12, phase: 11 },
  { id: 's12_export', number: 12, name: 'Video Export', description: 'Assembling compressed highlight video', engine: 'Temporal Intelligence Engine', icon: 'Download', estimatedDurationSeconds: 45, phase: 10 },
];

export const ENGINE_COLORS: Record<EngineType, string> = {
  'Perception Engine': '#3b82f6',
  'Semantic Intelligence Engine': '#8b5cf6',
  'Temporal Intelligence Engine': '#06b6d4',
};
