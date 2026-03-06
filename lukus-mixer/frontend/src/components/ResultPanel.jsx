import React, { useState, useEffect, useRef } from 'react';
import { Download, Upload, Plus, MoreHorizontal, FileAudio, ZoomIn, ZoomOut } from 'lucide-react';
import AudioPlayer from './AudioPlayer';

const STEM_COLORS = {
  vocals: 'green',
  drums: 'orange',
  bass: 'purple',
  guitar: 'cyan',
  piano: 'pink',
  other: 'slate',
};

const STEM_LABELS = {
  vocals: 'Vocals',
  drums: 'Drums',
  bass: 'Bass',
  guitar: 'Guitar',
  piano: 'Piano',
  other: 'Other',
};

const SPEC_HEIGHTS = { small: 50, normal: 80, large: 120 };

function fmtTime(seconds) {
  if (!seconds || !isFinite(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function Spectrogram({ src, label, height, currentTime, duration, onSeek }) {
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);
  const [hoverPos, setHoverPos] = useState(null);
  const [hoverTime, setHoverTime] = useState(null);

  useEffect(() => {
    setLoaded(false);
    setErrored(false);
    const img = new Image();
    img.onload = () => setLoaded(true);
    img.onerror = () => setErrored(true);
    img.src = src;
  }, [src]);

  const playheadPct = (duration && currentTime != null) ? (currentTime / duration) * 100 : null;

  const handleMouseMove = (e) => {
    if (!duration || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    setHoverPos(pct * 100);
    setHoverTime(pct * duration);
  };

  const handleMouseLeave = () => {
    setHoverPos(null);
    setHoverTime(null);
  };

  const handleClick = (e) => {
    if (!duration || !containerRef.current || !onSeek) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    onSeek(pct * duration);
  };

  if (errored) return null;

  return (
    <div
      ref={containerRef}
      className="mt-1.5 rounded overflow-hidden bg-[#0f172a] relative cursor-crosshair"
      style={{ height: `${height}px` }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      {!loaded ? (
        <div
          className="flex items-center justify-center text-dark-500 text-xs"
          style={{ height: `${height}px` }}
        >
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-dark-500 border-t-transparent rounded-full animate-spin" />
            스펙트로그램 로딩...
          </div>
        </div>
      ) : (
        <img
          ref={imgRef}
          src={src}
          alt={`${label} spectrogram`}
          className="w-full"
          style={{ height: `${height}px`, objectFit: 'fill' }}
          draggable={false}
        />
      )}

      {/* 재생 위치 플레이헤드 */}
      {loaded && playheadPct != null && playheadPct >= 0 && (
        <>
          <div
            className="absolute top-0 bottom-0 w-[2px] pointer-events-none z-10"
            style={{
              left: `${playheadPct}%`,
              background: 'rgba(255,255,255,0.85)',
              boxShadow: '0 0 4px rgba(255,255,255,0.5)',
            }}
          />
          <div
            className="absolute top-0 pointer-events-none z-10 bg-white/90 text-[#0f172a] text-[10px]
                       font-bold px-1.5 py-0.5 rounded-b-sm"
            style={{
              left: `${playheadPct}%`,
              transform: playheadPct > 90 ? 'translateX(-100%)' : 'translateX(-50%)',
            }}
          >
            {fmtTime(currentTime)}
          </div>
        </>
      )}

      {/* 호버 위치 표시 */}
      {loaded && hoverPos != null && (
        <>
          <div
            className="absolute top-0 bottom-0 w-[1px] pointer-events-none z-20"
            style={{
              left: `${hoverPos}%`,
              background: 'rgba(249,115,22,0.7)',
            }}
          />
          <div
            className="absolute bottom-0 pointer-events-none z-20 bg-orange-500/90 text-white text-[10px]
                       font-semibold px-1.5 py-0.5 rounded-t-sm"
            style={{
              left: `${hoverPos}%`,
              transform: hoverPos > 90 ? 'translateX(-100%)' : 'translateX(-50%)',
            }}
          >
            {fmtTime(hoverTime)}
          </div>
        </>
      )}
    </div>
  );
}

function ResultPanel({ results, jobId, uploadedFile, onDownload, onDownloadAll, onAddToLibrary, selectedStems = [] }) {
  const [specSize, setSpecSize] = useState('normal');
  const [stemTimes, setStemTimes] = useState({});
  const audioRefs = useRef({});

  const handleStemTimeUpdate = (stemName, time) => {
    setStemTimes(prev => ({ ...prev, [stemName]: time }));
  };

  const handleSpecSeek = (stemName, time) => {
    const audioEl = audioRefs.current[stemName];
    if (audioEl) {
      audioEl.currentTime = time;
    }
    setStemTimes(prev => ({ ...prev, [stemName]: time }));
  };

  if (!results) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8">
        <div className="w-20 h-20 bg-dark-800 rounded-2xl flex items-center justify-center mb-4">
          <Upload className="w-10 h-10 text-dark-600" />
        </div>
        <h3 className="text-lg font-semibold text-dark-400 mb-2">
          분리된 스템이 여기에 표시됩니다
        </h3>
        <p className="text-sm text-dark-500 text-center max-w-md">
          왼쪽에서 오디오 파일을 업로드하고 분리할 스템을 선택한 후<br />
          "Split Stems" 버튼을 클릭하세요.
        </p>
      </div>
    );
  }

  const stemKeys = Object.keys(results).filter(
    stem => selectedStems.length === 0 || selectedStems.includes(stem)
  );

  const specHeight = SPEC_HEIGHTS[specSize];

  const cycleSize = () => {
    const order = ['small', 'normal', 'large'];
    const idx = order.indexOf(specSize);
    setSpecSize(order[(idx + 1) % order.length]);
  };

  return (
    <div className="p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-orange-500/20 rounded-lg flex items-center justify-center">
            <FileAudio className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">
              {uploadedFile?.filename || 'Untitled'}
            </h2>
            <p className="text-sm text-dark-400">
              {formatDuration(uploadedFile?.duration)} • {stemKeys.length} stems
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={cycleSize}
            className="btn-secondary flex items-center gap-1.5 text-xs"
            title="스펙트로그램 크기 변경"
          >
            {specSize === 'large' ? <ZoomOut className="w-3.5 h-3.5" /> : <ZoomIn className="w-3.5 h-3.5" />}
            {specSize === 'small' ? 'S' : specSize === 'normal' ? 'M' : 'L'}
          </button>
          <button
            onClick={() => onAddToLibrary && onAddToLibrary()}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            Library
          </button>
          <button
            onClick={onDownloadAll}
            className="btn-secondary"
            title="전체 ZIP 다운로드"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 원본 파일 + 스펙트로그램 */}
      {uploadedFile && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-dark-300 mb-3">Original</h3>
          <AudioPlayer
            url={uploadedFile.url}
            title={uploadedFile.filename}
            duration={uploadedFile.duration}
            color="orange"
            onTimeUpdate={(t) => handleStemTimeUpdate('_original', t)}
            externalAudioRef={el => { audioRefs.current['_original'] = el; }}
          />
          {uploadedFile.file_id && (
            <Spectrogram
              src={`/api/spectrogram-original/${uploadedFile.file_id}`}
              label="Original"
              height={specHeight}
              currentTime={stemTimes['_original'] || 0}
              duration={uploadedFile.duration}
              onSeek={(t) => handleSpecSeek('_original', t)}
            />
          )}
        </div>
      )}

      {/* 분리된 스템들 */}
      <div>
        <h3 className="text-sm font-semibold text-dark-300 mb-3">
          Separated Stems ({stemKeys.length})
        </h3>

        <div className="space-y-3">
          {stemKeys.map(stemName => {
            const stem = results[stemName];
            const color = STEM_COLORS[stemName] || 'slate';
            const label = STEM_LABELS[stemName] || stemName;

            return (
              <div key={stemName} className="card p-3">
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <AudioPlayer
                      url={`/api/stream/${jobId}/${stemName}`}
                      title={label}
                      duration={stem.duration}
                      color={color}
                      onTimeUpdate={(t) => handleStemTimeUpdate(stemName, t)}
                      externalAudioRef={el => { audioRefs.current[stemName] = el; }}
                    />
                  </div>

                  <button
                    onClick={() => onDownload(stemName)}
                    className="p-2 text-dark-400 hover:text-white hover:bg-dark-700
                               rounded-lg transition-colors flex-shrink-0"
                    title={`${label} 다운로드`}
                  >
                    <Download className="w-5 h-5" />
                  </button>
                </div>

                <Spectrogram
                  src={`/api/spectrogram/${jobId}/${stemName}`}
                  label={label}
                  height={specHeight}
                  currentTime={stemTimes[stemName] || 0}
                  duration={stem.duration}
                  onSeek={(t) => handleSpecSeek(stemName, t)}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* 하단 액션 */}
      <div className="mt-8 pt-6 border-t border-dark-700">
        <div className="flex items-center justify-between">
          <p className="text-sm text-dark-500">
            모든 스템을 한 번에 다운로드하려면 ZIP 다운로드를 사용하세요.
          </p>
          <button
            onClick={onDownloadAll}
            className="btn-primary flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            <span>Download All (ZIP)</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function formatDuration(seconds) {
  if (!seconds) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default ResultPanel;
