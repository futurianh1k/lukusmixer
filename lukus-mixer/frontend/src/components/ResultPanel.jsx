import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Download, Upload, Plus, MoreHorizontal, FileAudio, ZoomIn, ZoomOut, X, Volume2, VolumeX, Minimize2, Music } from 'lucide-react';
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

const STEM_KR = {
  vocals: '보컬', drums: '드럼', bass: '베이스',
  guitar: '기타', piano: '피아노', other: '기타악기',
  Original: '전체',
};

const VOLUME_OPTIONS = [
  { label: '최대 (+12dB)', action: '최대로 크게', db: 12 },
  { label: '매우 크게 (+9dB)', action: '매우 크게', db: 9 },
  { label: '크게 (+6dB)', action: '크게', db: 6 },
  { label: '조금 크게 (+3dB)', action: '조금 크게', db: 3 },
  { label: '조금 작게 (-3dB)', action: '조금 작게', db: -3 },
  { label: '작게 (-6dB)', action: '작게', db: -6 },
  { label: '매우 작게 (-9dB)', action: '매우 작게', db: -9 },
  { label: '최소 (-12dB)', action: '최소로 작게', db: -12 },
  { label: '음소거', action: '음소거', db: -100 },
];

const SPEC_HEIGHTS = { small: 50, normal: 80, large: 120 };

function fmtTime(seconds) {
  if (!seconds || !isFinite(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// ────────────────────────────────────────────
// 스펙트로그램 팝업 모달
// ────────────────────────────────────────────
function SpectrogramModal({ src, label, duration, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-[90vw] max-w-[1400px] bg-dark-900 rounded-xl border border-dark-600
                   shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-dark-700">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-white">{label}</span>
            {duration && <span className="text-xs text-dark-500">{fmtTime(duration)}</span>}
          </div>
          <button onClick={onClose} className="text-dark-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 bg-[#0f172a]">
          <img
            src={src}
            alt={`${label} spectrogram`}
            className="w-full"
            style={{ height: '300px', objectFit: 'fill' }}
            draggable={false}
          />
        </div>
        <div className="px-5 py-2 border-t border-dark-700 text-[10px] text-dark-500">
          ESC 또는 바깥 클릭으로 닫기
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────
// 플로팅 볼륨 메뉴
// ────────────────────────────────────────────
function FloatingVolumeMenu({ x, y, onSelect, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, [onClose]);

  const menuStyle = {
    position: 'fixed',
    left: `${x}px`,
    top: `${y}px`,
    transform: 'translate(-50%, 8px)',
    zIndex: 200,
  };

  return (
    <div ref={ref} style={menuStyle}
         className="bg-dark-800 border border-dark-600 rounded-lg shadow-2xl p-1.5 min-w-[160px]">
      <div className="text-[9px] text-dark-500 uppercase tracking-wider px-2 py-1 mb-0.5">
        음량 조절 선택
      </div>
      {VOLUME_OPTIONS.map(opt => (
        <button
          key={opt.db}
          onClick={() => onSelect(opt)}
          className={`w-full text-left px-3 py-1.5 rounded text-xs transition-colors flex items-center gap-2
            ${opt.db <= -100
              ? 'hover:bg-red-500/20 text-red-400'
              : opt.db > 0
                ? 'hover:bg-green-500/20 text-green-400'
                : 'hover:bg-yellow-500/20 text-yellow-400'
            }`}
        >
          {opt.db <= -100 ? <VolumeX className="w-3 h-3" /> : <Volume2 className="w-3 h-3" />}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ────────────────────────────────────────────
// 스펙트로그램 컴포넌트
// ────────────────────────────────────────────
function Spectrogram({ src, label, stemName, height, currentTime, duration, onSeek, onAppendPrompt }) {
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const clickTimerRef = useRef(null);
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);
  const [hoverPos, setHoverPos] = useState(null);
  const [hoverTime, setHoverTime] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const [selectStart, setSelectStart] = useState(null);
  const [selectEnd, setSelectEnd] = useState(null);
  const [floatingMenu, setFloatingMenu] = useState(null);

  useEffect(() => {
    setLoaded(false);
    setErrored(false);
    const img = new Image();
    img.onload = () => setLoaded(true);
    img.onerror = () => setErrored(true);
    img.src = src;
  }, [src]);

  useEffect(() => {
    return () => { if (clickTimerRef.current) clearTimeout(clickTimerRef.current); };
  }, []);

  const playheadPct = (duration && currentTime != null) ? (currentTime / duration) * 100 : null;
  const startPct = (selectStart != null && duration) ? (selectStart / duration) * 100 : null;
  const endPct = (selectEnd != null && duration) ? (selectEnd / duration) * 100 : null;

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

  const getTimeFromEvent = (e) => {
    if (!duration || !containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    return Math.max(0, Math.min(duration, (x / rect.width) * duration));
  };

  const doSingleClick = (t, clientX) => {
    if (floatingMenu) return;

    if (selectStart == null) {
      setSelectStart(t);
      setSelectEnd(null);
    } else if (selectEnd == null) {
      const realStart = Math.min(selectStart, t);
      const realEnd = Math.max(selectStart, t);
      setSelectStart(realStart);
      setSelectEnd(realEnd);

      const rect = containerRef.current?.getBoundingClientRect();
      if (rect) {
        setFloatingMenu({
          x: clientX,
          y: rect.bottom,
          start: realStart,
          end: realEnd,
        });
      }
    } else {
      setSelectStart(t);
      setSelectEnd(null);
      setFloatingMenu(null);
    }
  };

  const handleClick = (e) => {
    const t = getTimeFromEvent(e);
    if (t == null) return;
    const cx = e.clientX;

    if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
    clickTimerRef.current = setTimeout(() => {
      doSingleClick(t, cx);
    }, 250);
  };

  const handleDoubleClick = (e) => {
    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
    }
    e.preventDefault();
    setSelectStart(null);
    setSelectEnd(null);
    setFloatingMenu(null);
    setShowModal(true);
  };

  const handleVolumeSelect = (opt) => {
    if (onAppendPrompt && floatingMenu) {
      const kr = STEM_KR[stemName] || label;
      const line = `${Math.floor(floatingMenu.start)}초~${Math.floor(floatingMenu.end)}초 ${kr} ${opt.action}`;
      onAppendPrompt(line);
    }
    setFloatingMenu(null);
    setSelectStart(null);
    setSelectEnd(null);
  };

  const handleMenuClose = () => {
    setFloatingMenu(null);
    setSelectStart(null);
    setSelectEnd(null);
  };

  if (errored) return null;

  return (
    <>
      <div
        ref={containerRef}
        className="mt-1.5 rounded overflow-hidden bg-[#0f172a] relative cursor-crosshair select-none"
        style={{ height: `${height}px` }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
      >
        {!loaded ? (
          <div className="flex items-center justify-center text-dark-500 text-xs"
               style={{ height: `${height}px` }}>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-dark-500 border-t-transparent rounded-full animate-spin" />
              스펙트로그램 로딩...
            </div>
          </div>
        ) : (
          <img ref={imgRef} src={src} alt={`${label} spectrogram`}
               className="w-full" style={{ height: `${height}px`, objectFit: 'fill' }}
               draggable={false} />
        )}

        {/* 선택 구간 하이라이트 */}
        {loaded && startPct != null && endPct != null && (
          <div className="absolute top-0 bottom-0 pointer-events-none z-[5]"
               style={{
                 left: `${startPct}%`,
                 width: `${endPct - startPct}%`,
                 background: 'rgba(249,115,22,0.15)',
                 borderLeft: '2px solid rgba(249,115,22,0.8)',
                 borderRight: '2px solid rgba(249,115,22,0.8)',
               }} />
        )}

        {/* 시작점 마커 */}
        {loaded && startPct != null && (
          <div className="absolute top-0 pointer-events-none z-[15] bg-green-500/90 text-white text-[9px]
                         font-bold px-1 py-0.5 rounded-br-sm" style={{ left: `${startPct}%` }}>
            S {fmtTime(selectStart)}
          </div>
        )}

        {/* 끝점 마커 */}
        {loaded && endPct != null && (
          <div className="absolute top-0 pointer-events-none z-[15] bg-red-500/90 text-white text-[9px]
                         font-bold px-1 py-0.5 rounded-bl-sm"
               style={{ left: `${endPct}%`, transform: 'translateX(-100%)' }}>
            E {fmtTime(selectEnd)}
          </div>
        )}

        {/* 시작점만 있을 때 안내 */}
        {loaded && selectStart != null && selectEnd == null && (
          <div className="absolute bottom-1 left-1/2 -translate-x-1/2 pointer-events-none z-[15]
                         bg-dark-800/90 text-dark-300 text-[9px] px-2 py-0.5 rounded">
            끝 지점을 클릭하세요
          </div>
        )}

        {/* 재생 위치 플레이헤드 */}
        {loaded && playheadPct != null && playheadPct >= 0 && (
          <>
            <div className="absolute top-0 bottom-0 w-[2px] pointer-events-none z-10"
                 style={{ left: `${playheadPct}%`, background: 'rgba(255,255,255,0.85)',
                          boxShadow: '0 0 4px rgba(255,255,255,0.5)' }} />
            <div className="absolute top-0 pointer-events-none z-10 bg-white/90 text-[#0f172a] text-[10px]
                           font-bold px-1.5 py-0.5 rounded-b-sm"
                 style={{ left: `${playheadPct}%`,
                          transform: playheadPct > 90 ? 'translateX(-100%)' : 'translateX(-50%)' }}>
              {fmtTime(currentTime)}
            </div>
          </>
        )}

        {/* 호버 위치 표시 */}
        {loaded && hoverPos != null && (
          <>
            <div className="absolute top-0 bottom-0 w-[1px] pointer-events-none z-20"
                 style={{ left: `${hoverPos}%`, background: 'rgba(249,115,22,0.7)' }} />
            <div className="absolute bottom-0 pointer-events-none z-20 bg-orange-500/90 text-white text-[10px]
                           font-semibold px-1.5 py-0.5 rounded-t-sm"
                 style={{ left: `${hoverPos}%`,
                          transform: hoverPos > 90 ? 'translateX(-100%)' : 'translateX(-50%)' }}>
              {fmtTime(hoverTime)}
            </div>
          </>
        )}
      </div>

      {/* 플로팅 볼륨 메뉴 */}
      {floatingMenu && (
        <FloatingVolumeMenu
          x={floatingMenu.x} y={floatingMenu.y}
          onSelect={handleVolumeSelect} onClose={handleMenuClose}
        />
      )}

      {/* 팝업 모달 */}
      {showModal && (
        <SpectrogramModal
          src={src} label={label} duration={duration}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}

function ResultPanel({ results, jobId, uploadedFile, onDownload, onDownloadAll, onAddToLibrary, selectedStems = [], onAppendPrompt, expandedMix, onCloseExpandedMix }) {
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
              stemName="Original"
              height={specHeight}
              currentTime={stemTimes['_original'] || 0}
              duration={uploadedFile.duration}
              onSeek={(t) => handleSpecSeek('_original', t)}
              onAppendPrompt={onAppendPrompt}
            />
          )}
        </div>
      )}

      {/* 확대된 Mix Result 플로팅 플레이어 */}
      {expandedMix && (
        <div className="mb-6 bg-gradient-to-r from-orange-500/10 to-orange-600/5 rounded-xl
                       border border-orange-500/30 p-4 shadow-lg shadow-orange-500/5
                       animate-in slide-in-from-top">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-orange-500/20 rounded-lg flex items-center justify-center">
                <Music className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-orange-300">Mixed Result</h3>
                <p className="text-[10px] text-dark-500">
                  {expandedMix.duration ? fmtTime(expandedMix.duration) : ''}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => expandedMix.jobId && expandedMix.mixId &&
                  window.open(`/api/download-mix/${expandedMix.jobId}/${expandedMix.mixId}`, '_blank')}
                className="p-1.5 rounded hover:bg-dark-700 text-dark-400 hover:text-white transition-colors"
                title="다운로드"
              >
                <Download className="w-4 h-4" />
              </button>
              <button
                onClick={onCloseExpandedMix}
                className="p-1.5 rounded hover:bg-dark-700 text-dark-400 hover:text-white transition-colors"
                title="축소"
              >
                <Minimize2 className="w-4 h-4" />
              </button>
            </div>
          </div>
          <AudioPlayer
            url={expandedMix.url}
            title={expandedMix.title || 'Mixed Result'}
            duration={expandedMix.duration}
            color="orange"
          />
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
                  stemName={stemName}
                  height={specHeight}
                  currentTime={stemTimes[stemName] || 0}
                  duration={stem.duration}
                  onSeek={(t) => handleSpecSeek(stemName, t)}
                  onAppendPrompt={onAppendPrompt}
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
