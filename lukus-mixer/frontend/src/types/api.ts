/**
 * LUKUS Music Mixer — API 타입 정의
 *
 * 백엔드 main.py의 Pydantic 모델과 1:1 대응.
 * .jsx → .tsx 점진적 마이그레이션 시 이 타입들을 import하여 사용.
 */

import type { ReactNode, RefObject, MutableRefObject } from 'react';

// ────────────────────────────────────────────
// API 응답 타입
// ────────────────────────────────────────────

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

export type JobStatusType = 'pending' | 'processing' | 'completed' | 'failed';

export interface JobStatus {
  job_id: string;
  status: JobStatusType;
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
  status: JobStatusType;
  progress: number;
  message: string;
  result: Record<string, StemResult> | null;
  logs: string[] | null;
}

// ────────────────────────────────────────────
// 컴포넌트 Props 타입
// ────────────────────────────────────────────

export interface ErrorBoundaryProps {
  name?: string;
  children: ReactNode;
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export type AudioPlayerColor = 'lukus' | 'green' | 'orange' | 'purple' | 'cyan' | 'pink' | 'slate' | 'emerald' | 'amber' | 'violet' | 'fuchsia' | 'yellow' | 'lime';

export interface AudioPlayerProps {
  url: string;
  title: string;
  duration?: number;
  color?: AudioPlayerColor;
  onTimeUpdate?: (time: number) => void;
  externalAudioRef?: ((el: HTMLAudioElement | null) => void) | RefObject<HTMLAudioElement | null>;
  children?: ReactNode;
}

export interface FileUploadProps {
  onUpload: (file: File) => void;
  uploadedFile: UploadedFile | null;
  onRemove?: () => void;
}

export interface StemSelectorProps {
  availableStems: string[];
  selectedStems: string[];
  onChange: (stems: string[]) => void;
}

export interface MixingPanelProps {
  results: Record<string, StemResult> | null;
  jobId: string | null;
  duration?: number;
  onAddToLibrary?: (mixId?: string) => void;
  originalFilename?: string;
  externalPromptAppend?: { text: string; id: number } | null;
  onExpandMixResult?: (mix: ExpandedMix) => void;
}

export interface ResultPanelProps {
  results: Record<string, StemResult> | null;
  jobId: string | null;
  uploadedFile: UploadedFile | null;
  onDownload: (stemName: string) => void;
  onDownloadAll: () => void;
  onAddToLibrary?: (mixId?: string) => void;
  selectedStems?: string[];
  onAppendPrompt?: (text: string) => void;
  expandedMix?: ExpandedMix | null;
  onCloseExpandedMix?: () => void;
}

export interface SpectrogramProps {
  src: string;
  label: string;
  stemName: string;
  height: number;
  currentTime?: number;
  duration?: number;
  onSeek?: (time: number) => void;
  onAppendPrompt?: (text: string) => void;
}

// ────────────────────────────────────────────
// WebSocket 훅 타입
// ────────────────────────────────────────────

export interface UseJobWebSocketCallbacks {
  onUpdate?: (data: WsJobUpdate) => void;
  onComplete?: (data: WsJobUpdate) => void;
  onFailed?: (data: WsJobUpdate) => void;
}

export interface UseJobWebSocketReturn {
  usingFallback: boolean;
}

// ────────────────────────────────────────────
// 유틸리티 타입
// ────────────────────────────────────────────

export interface VolumeOption {
  label: string;
  action: string;
  db: number;
}

export interface HistoryItem {
  filename: string;
  prompt: string;
  created_at: string;
  size: number;
}

export interface PromptHistoryResponse {
  items: HistoryItem[];
}
