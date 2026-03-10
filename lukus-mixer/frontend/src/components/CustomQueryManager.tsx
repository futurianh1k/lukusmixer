/**
 * CustomQueryManager — 사용자 커스텀 쿼리 관리 컴포넌트
 * 
 * Banquet 모델의 쿼리 기반 분리 기능을 확장하여
 * 사용자가 직접 쿼리 오디오를 업로드하고 관리할 수 있습니다.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  Music2,
  Trash2,
  Play,
  Pause,
  Check,
  X,
  Palette,
  Edit2,
  Plus,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type {
  CustomQuery,
  CustomQueryListResponse,
  CustomQueryUploadResponse,
  QUERY_COLOR_PRESETS,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const COLOR_PRESETS: readonly string[] = [
  '#22c55e', '#f97316', '#8b5cf6', '#06b6d4', '#ec4899',
  '#eab308', '#3b82f6', '#ef4444', '#a78bfa', '#14b8a6',
];

interface CustomQueryManagerProps {
  onQuerySelect: (queryIds: string[]) => void;
  selectedQueryIds: string[];
  disabled?: boolean;
  banquetAvailable?: boolean;
}

interface QueryItemProps {
  query: CustomQuery;
  isSelected: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onUpdate: (updates: Partial<CustomQuery>) => void;
  disabled: boolean;
}

function QueryItem({
  query,
  isSelected,
  onToggle,
  onDelete,
  onUpdate,
  disabled,
}: QueryItemProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(query.name);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const streamUrl = `${API_BASE}/api/custom-queries/${query.query_id}/stream`;

  const handlePlayPause = useCallback(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio(streamUrl);
      audioRef.current.onended = () => setIsPlaying(false);
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying, streamUrl]);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handleSaveName = () => {
    if (editName.trim() && editName !== query.name) {
      onUpdate({ name: editName.trim() });
    }
    setIsEditing(false);
  };

  const handleColorChange = (color: string) => {
    onUpdate({ color });
    setShowColorPicker(false);
  };

  return (
    <div
      className={`
        relative flex items-center gap-3 p-3 rounded-lg border transition-all
        ${isSelected
          ? 'border-violet-500 bg-violet-500/10'
          : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
        }
        ${disabled ? 'opacity-50 pointer-events-none' : ''}
      `}
    >
      {/* 선택 체크박스 */}
      <button
        onClick={onToggle}
        className={`
          flex-shrink-0 w-6 h-6 rounded-md border-2 flex items-center justify-center
          transition-colors
          ${isSelected
            ? 'bg-violet-500 border-violet-500'
            : 'border-slate-600 hover:border-violet-400'
          }
        `}
      >
        {isSelected && <Check className="w-4 h-4 text-white" />}
      </button>

      {/* 색상 인디케이터 */}
      <div className="relative">
        <button
          onClick={() => setShowColorPicker(!showColorPicker)}
          className="w-8 h-8 rounded-full border-2 border-slate-600 hover:border-slate-400 transition-colors"
          style={{ backgroundColor: query.color }}
          title="색상 변경"
        >
          <Palette className="w-4 h-4 text-white/70 mx-auto" />
        </button>

        {/* 색상 선택기 */}
        {showColorPicker && (
          <div className="absolute top-10 left-0 z-20 bg-slate-800 border border-slate-700 rounded-lg p-2 shadow-xl">
            <div className="grid grid-cols-5 gap-1">
              {COLOR_PRESETS.map((color) => (
                <button
                  key={color}
                  onClick={() => handleColorChange(color)}
                  className={`w-6 h-6 rounded-full border-2 transition-transform hover:scale-110 ${
                    query.color === color ? 'border-white' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 쿼리 정보 */}
      <div className="flex-1 min-w-0">
        {isEditing ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-white"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveName();
                if (e.key === 'Escape') setIsEditing(false);
              }}
            />
            <button
              onClick={handleSaveName}
              className="p-1 text-green-400 hover:text-green-300"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              onClick={() => setIsEditing(false)}
              className="p-1 text-slate-400 hover:text-slate-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="font-medium text-white truncate">{query.name}</span>
            <button
              onClick={() => setIsEditing(true)}
              className="p-1 text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100"
            >
              <Edit2 className="w-3 h-3" />
            </button>
          </div>
        )}
        <div className="text-xs text-slate-400 mt-0.5">
          {query.duration ? `${query.duration.toFixed(1)}초` : '—'}
          {query.description && ` · ${query.description}`}
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="flex items-center gap-1">
        <button
          onClick={handlePlayPause}
          className={`p-2 rounded-lg transition-colors ${
            isPlaying
              ? 'bg-violet-500 text-white'
              : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
          }`}
          title={isPlaying ? '정지' : '미리듣기'}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <button
          onClick={onDelete}
          className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-red-500/20 hover:text-red-400 transition-colors"
          title="삭제"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export default function CustomQueryManager({
  onQuerySelect,
  selectedQueryIds,
  disabled = false,
  banquetAvailable = true,
}: CustomQueryManagerProps) {
  const [queries, setQueries] = useState<CustomQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isExpanded, setIsExpanded] = useState(true);
  const [uploadName, setUploadName] = useState('');
  const [uploadColor, setUploadColor] = useState(COLOR_PRESETS[0]);

  const fetchQueries = useCallback(async () => {
    try {
      const res = await axios.get<CustomQueryListResponse>(
        `${API_BASE}/api/custom-queries`
      );
      setQueries(res.data.queries);
    } catch (err) {
      console.error('쿼리 목록 조회 실패:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueries();
  }, [fetchQueries]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setUploading(true);
      setUploadProgress(0);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', uploadName || file.name.replace(/\.[^/.]+$/, ''));
      formData.append('color', uploadColor);

      try {
        const res = await axios.post<CustomQueryUploadResponse>(
          `${API_BASE}/api/custom-queries/upload`,
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (e) => {
              if (e.total) {
                setUploadProgress(Math.round((e.loaded / e.total) * 100));
              }
            },
          }
        );

        await fetchQueries();
        setUploadName('');
        setUploadColor(COLOR_PRESETS[Math.floor(Math.random() * COLOR_PRESETS.length)]);
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        alert(error.response?.data?.detail || '업로드 실패');
      } finally {
        setUploading(false);
        setUploadProgress(0);
      }
    },
    [fetchQueries, uploadName, uploadColor]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.mp3', '.wav', '.flac', '.ogg', '.m4a'],
    },
    maxFiles: 1,
    disabled: disabled || uploading,
  });

  const handleToggleQuery = (queryId: string) => {
    const newSelection = selectedQueryIds.includes(queryId)
      ? selectedQueryIds.filter((id) => id !== queryId)
      : [...selectedQueryIds, queryId];
    onQuerySelect(newSelection);
  };

  const handleDeleteQuery = async (queryId: string) => {
    if (!confirm('이 쿼리를 삭제하시겠습니까?')) return;

    try {
      await axios.delete(`${API_BASE}/api/custom-queries/${queryId}`);
      setQueries((prev) => prev.filter((q) => q.query_id !== queryId));
      onQuerySelect(selectedQueryIds.filter((id) => id !== queryId));
    } catch (err) {
      console.error('쿼리 삭제 실패:', err);
      alert('삭제 실패');
    }
  };

  const handleUpdateQuery = async (
    queryId: string,
    updates: Partial<CustomQuery>
  ) => {
    try {
      await axios.patch(`${API_BASE}/api/custom-queries/${queryId}`, updates);
      setQueries((prev) =>
        prev.map((q) => (q.query_id === queryId ? { ...q, ...updates } : q))
      );
    } catch (err) {
      console.error('쿼리 업데이트 실패:', err);
    }
  };

  if (!banquetAvailable) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
        <div className="flex items-center gap-2 text-amber-400">
          <Music2 className="w-5 h-5" />
          <span className="font-medium">Banquet 모델 사용 불가</span>
        </div>
        <p className="text-sm text-slate-400 mt-2">
          커스텀 쿼리 기능을 사용하려면 Banquet 체크포인트를 설치해주세요.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
      {/* 헤더 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Music2 className="w-5 h-5 text-white" />
          </div>
          <div className="text-left">
            <h3 className="font-semibold text-white">커스텀 쿼리</h3>
            <p className="text-xs text-slate-400">
              {queries.length}개 쿼리 · {selectedQueryIds.length}개 선택됨
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-slate-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400" />
        )}
      </button>

      {isExpanded && (
        <div className="p-4 pt-0 space-y-4">
          {/* 업로드 영역 */}
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="쿼리 이름 (선택)"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500"
                disabled={disabled || uploading}
              />
              <div className="flex items-center gap-1 bg-slate-700/50 border border-slate-600 rounded-lg px-2">
                {COLOR_PRESETS.slice(0, 5).map((color) => (
                  <button
                    key={color}
                    onClick={() => setUploadColor(color)}
                    className={`w-5 h-5 rounded-full transition-transform ${
                      uploadColor === color ? 'scale-125 ring-2 ring-white' : ''
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>

            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all
                ${isDragActive
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-slate-600 hover:border-slate-500'
                }
                ${disabled || uploading ? 'opacity-50 cursor-not-allowed' : ''}
              `}
            >
              <input {...getInputProps()} />
              {uploading ? (
                <div className="space-y-2">
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div
                      className="bg-violet-500 h-2 rounded-full transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-sm text-slate-400">업로드 중... {uploadProgress}%</p>
                </div>
              ) : (
                <>
                  <Upload className="w-8 h-8 mx-auto text-slate-500 mb-2" />
                  <p className="text-sm text-slate-400">
                    {isDragActive
                      ? '여기에 드롭하세요'
                      : '쿼리 오디오를 드래그하거나 클릭하여 업로드'}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    MP3, WAV, FLAC · 최대 30초 · 20MB
                  </p>
                </>
              )}
            </div>
          </div>

          {/* 쿼리 목록 */}
          {loading ? (
            <div className="text-center py-4 text-slate-400">로딩 중...</div>
          ) : queries.length === 0 ? (
            <div className="text-center py-6 text-slate-500">
              <Music2 className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>등록된 커스텀 쿼리가 없습니다</p>
              <p className="text-xs mt-1">원하는 악기 소리를 업로드해보세요!</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {queries.map((query) => (
                <QueryItem
                  key={query.query_id}
                  query={query}
                  isSelected={selectedQueryIds.includes(query.query_id)}
                  onToggle={() => handleToggleQuery(query.query_id)}
                  onDelete={() => handleDeleteQuery(query.query_id)}
                  onUpdate={(updates) => handleUpdateQuery(query.query_id, updates)}
                  disabled={disabled}
                />
              ))}
            </div>
          )}

          {/* 선택된 쿼리 요약 */}
          {selectedQueryIds.length > 0 && (
            <div className="bg-violet-500/10 border border-violet-500/30 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-violet-300">
                  {selectedQueryIds.length}개 쿼리 선택됨
                </span>
                <button
                  onClick={() => onQuerySelect([])}
                  className="text-xs text-violet-400 hover:text-violet-300"
                >
                  선택 해제
                </button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {selectedQueryIds.map((id) => {
                  const q = queries.find((x) => x.query_id === id);
                  return q ? (
                    <span
                      key={id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs text-white"
                      style={{ backgroundColor: q.color + '40' }}
                    >
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: q.color }}
                      />
                      {q.name}
                    </span>
                  ) : null;
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
