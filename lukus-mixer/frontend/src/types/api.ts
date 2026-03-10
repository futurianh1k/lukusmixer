/**
 * LUKUS Music Mixer — API 타입 정의
 *
 * 백엔드 main.py의 Pydantic 모델과 1:1 대응.
 * .jsx → .tsx 점진적 마이그레이션 시 이 타입들을 import하여 사용.
 */

export interface ModelInfo {
  id: string;
  name: string;
  stems: string[];
  engine: 'demucs' | 'chained' | 'chained_10s' | 'chained_banquet';
  description: string;
}

export interface SystemInfo {
  cuda_available: boolean;
  demucs_available: boolean;
  audio_separator_available: boolean;
  banquet_available: boolean;
  models: ModelInfo[];
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  duration: number;
  size: number;
}

export interface StemResult {
  name: string;
  path: string;
  duration: number;
  spectrogram: string | null;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  result: Record<string, StemResult> | null;
  logs: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface MixCommand {
  instrument: string;
  start_sec: number;
  end_sec: number;
  volume_db: number;
  original_text: string;
}

export interface MixResponse {
  mix_id: string;
  commands: MixCommand[];
  stream_url: string;
}

export interface UploadedFile extends UploadResponse {
  file: File;
  url: string;
}

export interface ExpandedMix {
  url: string;
  title: string;
  duration: number;
  jobId: string;
  mixId: string;
}

export interface WsJobUpdate {
  type: 'job_update';
  job_id: string;
  status: JobStatus['status'];
  progress: number;
  message: string;
  result: Record<string, StemResult> | null;
  logs: string[] | null;
}

// ───────────────────────────────────────────────
// Custom Query (Banquet 확장)
// ───────────────────────────────────────────────

export interface CustomQuery {
  query_id: string;
  name: string;
  description: string;
  file_path: string;
  color: string;
  duration: number | null;
  created_at: string;
  updated_at: string;
}

export interface CustomQueryUploadResponse {
  query_id: string;
  name: string;
  description: string;
  color: string;
  duration: number | null;
  message: string;
}

export interface CustomQueryListResponse {
  queries: CustomQuery[];
}

export interface CustomSplitRequest {
  query_ids: string[];
}

export interface CustomSplitResponse {
  job_id: string;
  status: string;
  stems: string[];
}

export interface CustomStemResult extends StemResult {
  color: string;
  query_id: string;
}

// CustomQueryManager 컴포넌트 Props
export interface CustomQueryManagerProps {
  onQuerySelect: (queryIds: string[]) => void;
  selectedQueryIds: string[];
  disabled?: boolean;
}

// CustomQueryUpload 컴포넌트 Props  
export interface CustomQueryUploadProps {
  onUploadComplete: (query: CustomQuery) => void;
  disabled?: boolean;
}

// 쿼리 색상 프리셋
export const QUERY_COLOR_PRESETS = [
  '#22c55e', // green
  '#f97316', // orange
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#eab308', // yellow
  '#3b82f6', // blue
  '#ef4444', // red
  '#a78bfa', // purple
  '#14b8a6', // teal
] as const;
