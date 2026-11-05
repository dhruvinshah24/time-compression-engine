/**
 * TCE v1.1 - Domain Entity Type Definitions
 */

export type EngineType =
  | 'Perception Engine'
  | 'Semantic Intelligence Engine'
  | 'Temporal Intelligence Engine';

export type PipelineStageCode =
  | 'S01' | 'S02' | 'S03' | 'S04' | 'S05' | 'S06'
  | 'S07' | 'S08' | 'S09' | 'S10' | 'S11' | 'S12';

export interface StageTiming {
  stage: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  duration_seconds: number;
  progress?: number;
  details?: string;
}

export interface JobRecord {
  id: string;
  video_id: string;
  filename: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  event_count: number;
  current_stage?: string;
  error?: string | null;
  created_at?: string;
  completed_at?: string;
  video_metadata?: {
    profile?: string;
    duration_hms?: string;
    duration_seconds?: number;
    resolution?: string;
    fps?: number;
    frame_count?: number;
  };
}

export interface TimelineEvidence {
  zone_id?: string;
  direction?: string;
  lighting_condition?: string;
  preprocessing_mode?: string;
  event_frame_path?: string;
  raw_metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface TimelineEvent {
  id?: string;
  event_id?: string;
  type?: string;
  event_type?: string;
  timestamp_ms?: number;
  start_ms: number;
  end_ms?: number;
  confidence?: number;
  video_id?: string;
  person_label?: string;
  display_name?: string;
  rule_name?: string;
  description?: string;
  thumbnail_path?: string;
  clip_path?: string;
  evidence?: TimelineEvidence;
}

export interface PersonRecord {
  person_label: string;
  track_ids: number[];
  first_seen_ms: number;
  last_seen_ms: number;
  observation_count: number;
  entry_direction?: string;
  crop_url?: string;
  context_url?: string;
}

export interface VideoRecord {
  id: string;
  filename: string;
  duration_seconds: number;
  duration_hms?: string;
  resolution?: string;
  fps?: number;
  frame_count?: number;
  status: string;
  event_count?: number;
  source_domain?: string;
  thumbnail_path?: string;
  created_at?: string;
}

export interface AnalyticsStats {
  total_videos: number;
  total_events: number;
  avg_compression_ratio: number;
  total_bytes_uploaded: number;
  hours_saved: number;
}

export interface SystemSetting {
  key: string;
  category: string;
  name: string;
  value: string | number | boolean;
  description: string;
  unit?: string;
}

export interface StoryArc {
  arc_id: string;
  person_label: string;
  track_id: number;
  events: TimelineEvent[];
  start_ms: number;
  end_ms: number;
  duration_s: number;
  event_count: number;
  avg_confidence: number;
  crop_url?: string;
}
