import React, { useState, useMemo, useEffect } from 'react';
import { Mic2, Drum, Guitar, Piano, Waves, Music, Volume2, VolumeX, Play, Loader2, Download, Plus, Trash2, Save, History, X, Clock, Maximize2 } from 'lucide-react';
import AudioPlayer from './AudioPlayer';
import axios from 'axios';

const API_BASE = '/api';

const STEM_CONFIG = {
  vocals:         { label: '보컬', en: 'Vocals', icon: Mic2,   color: 'green' },
  lead_vocals:    { label: '리드보컬', en: 'Lead Vocals', icon: Mic2,   color: 'green' },
  backing_vocals: { label: '백킹보컬', en: 'Backing Vocals', icon: Mic2, color: 'green' },
  drums:          { label: '드럼', en: 'Drums',  icon: Drum,   color: 'orange' },
  kick:           { label: '킥', en: 'Kick',    icon: Drum,   color: 'orange' },
  snare:          { label: '스네어', en: 'Snare', icon: Drum,   color: 'orange' },
  toms:           { label: '탐', en: 'Toms',    icon: Drum,   color: 'orange' },
  cymbals:        { label: '심벌즈', en: 'Cymbals', icon: Drum, color: 'yellow' },
  bass:           { label: '베이스', en: 'Bass', icon: Waves,  color: 'purple' },
  guitar:         { label: '기타', en: 'Guitar', icon: Guitar, color: 'cyan' },
  piano:          { label: '피아노', en: 'Piano', icon: Piano,  color: 'pink' },
  other:          { label: '기타악기', en: 'Other', icon: Music, color: 'slate' },
};

const VOLUME_PRESETS = [
  { label: '최대 (+12dB)',     db: 12 },
  { label: '매우 크게 (+9dB)', db: 9 },
  { label: '크게 (+6dB)',      db: 6 },
  { label: '조금 크게 (+3dB)', db: 3 },
  { label: '원본 (0dB)',       db: 0 },
  { label: '조금 작게 (-3dB)', db: -3 },
  { label: '작게 (-6dB)',      db: -6 },
  { label: '매우 작게 (-9dB)', db: -9 },
  { label: '최소 (-12dB)',     db: -12 },
  { label: '음소거',           db: -100 },
];

function MixingPanel({ results, jobId, duration, onAddToLibrary, originalFilename, externalPromptAppend, onExpandMixResult }) {
  const [selectedInstrument, setSelectedInstrument] = useState('');
  const [startSec, setStartSec] = useState(0);
  const [endSec, setEndSec] = useState(15);
  const [volumePreset, setVolumePreset] = useState(6);
  const [prompt, setPrompt] = useState('');
  const [parsedCommands, setParsedCommands] = useState([]);
  const [isMixing, setIsMixing] = useState(false);
  const [mixProgress, setMixProgress] = useState(0);
  const [mixResult, setMixResult] = useState(null);
  const [mixId, setMixId] = useState(null);
  const [mixLog, setMixLog] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [lastAppendId, setLastAppendId] = useState(0);

  useEffect(() => {
    if (externalPromptAppend && externalPromptAppend.id !== lastAppendId) {
      setPrompt(prev => prev ? prev + '\n' + externalPromptAppend.text : externalPromptAppend.text);
      setLastAppendId(externalPromptAppend.id);
    }
  }, [externalPromptAppend, lastAppendId]);

  const availableStems = useMemo(() => {
    return results ? Object.keys(results) : [];
  }, [results]);

  const maxDuration = duration || 180;

  const clearPrompt = () => {
    setPrompt('');
    setParsedCommands([]);
    setMixResult(null);
    setMixId(null);
    setMixLog('');
    setMixProgress(0);
  };

  const loadHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE}/prompt-history`);
      setHistoryItems(res.data.items || []);
    } catch (err) {
      console.error('히스토리 로드 실패:', err);
    }
  };

  const savePromptToHistory = async () => {
    if (!prompt.trim()) return;
    setSavingPrompt(true);
    try {
      const res = await axios.post(`${API_BASE}/prompt-history/save`, {
        prompt: prompt.trim(),
        original_filename: originalFilename || 'prompt',
        mix_result_info: mixLog || '',
      });
      alert(res.data.message);
      loadHistory();
    } catch (err) {
      alert('저장 실패: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingPrompt(false);
    }
  };

  const loadPromptFromHistory = (item) => {
    setPrompt(item.prompt);
    setShowHistory(false);
  };

  const deleteHistoryItem = async (filename, e) => {
    e.stopPropagation();
    if (!confirm(`"${filename}" 를 삭제하시겠습니까?`)) return;
    try {
      await axios.delete(`${API_BASE}/prompt-history/${filename}`);
      setHistoryItems(prev => prev.filter(h => h.filename !== filename));
    } catch (err) {
      alert('삭제 실패');
    }
  };

  useEffect(() => {
    if (showHistory) loadHistory();
  }, [showHistory]);

  const addToPrompt = () => {
    if (!selectedInstrument) return;
    const cfg = STEM_CONFIG[selectedInstrument];
    const krName = cfg?.label || selectedInstrument;
    const preset = VOLUME_PRESETS.find(p => p.db === volumePreset);
    const actionText = preset?.label.split('(')[0].trim() || '';

    let line;
    if (startSec === 0 && endSec >= maxDuration) {
      line = `${krName} ${actionText}`;
    } else {
      line = `${startSec}초~${endSec}초 ${krName} ${actionText}`;
    }
    setPrompt(prev => prev ? prev + '\n' + line : line);
  };

  const handleParsePreview = async () => {
    if (!prompt.trim() || !jobId) return;
    try {
      const res = await axios.post(`${API_BASE}/parse-prompt/${jobId}`, { prompt });
      setParsedCommands(res.data.commands);
    } catch (err) {
      console.error('파싱 오류:', err);
    }
  };

  const handleMix = async () => {
    if (!prompt.trim() || !jobId) return;
    setIsMixing(true);
    setMixResult(null);
    setMixProgress(10);
    setMixLog('AI 믹싱 실행 중...');

    try {
      setMixProgress(30);
      const res = await axios.post(`${API_BASE}/mix/${jobId}`, { prompt });
      setMixProgress(90);
      setParsedCommands(res.data.commands);
      setMixResult(res.data.stream_url);
      setMixId(res.data.mix_id);
      setMixProgress(100);
      const cmdSummary = res.data.commands.map(c => 
        `  • ${STEM_CONFIG[c.instrument]?.label || c.instrument}: ${c.start_sec.toFixed(0)}~${c.end_sec.toFixed(0)}초, ${c.volume_db > 0 ? '+' : ''}${c.volume_db}dB`
      ).join('\n');
      setMixLog(`✅ AI 믹싱 완료!\n\n파싱된 명령 (${res.data.commands.length}개):\n${cmdSummary}`);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setMixProgress(0);
      setMixLog(`❌ 오류: ${detail}`);
    } finally {
      setIsMixing(false);
    }
  };

  if (!results) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <p className="text-dark-500 text-sm text-center">
          STEM 분리가 완료되면<br />프롬프트 믹싱을 사용할 수 있습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="p-5 flex flex-col gap-5 h-full overflow-y-auto">
      <h2 className="text-lg font-bold text-white">Prompt Mixing</h2>

      {/* 검출된 악기 스템 */}
      <div>
        <h3 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2">
          검출된 악기 Stems
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {availableStems.map(stem => {
            const cfg = STEM_CONFIG[stem];
            const Icon = cfg?.icon || Music;
            const isSelected = selectedInstrument === stem;
            const colorClass = {
              green: 'bg-green-500/20 text-green-400 border-green-500/50',
              orange: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
              purple: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
              cyan: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50',
              pink: 'bg-pink-500/20 text-pink-400 border-pink-500/50',
              slate: 'bg-slate-500/20 text-slate-400 border-slate-500/50',
            }[cfg?.color || 'slate'];

            return (
              <button
                key={stem}
                onClick={() => setSelectedInstrument(stem)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                  border transition-all
                  ${isSelected ? `${colorClass} ring-1 ring-white/30` : 'bg-dark-800 text-dark-400 border-dark-700 hover:border-dark-500'}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {cfg?.label || stem}
              </button>
            );
          })}
        </div>
      </div>

      {/* 구간 & 볼륨 선택 */}
      <div className="bg-dark-800/50 rounded-lg p-4 border border-dark-700">
        <h3 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-3">
          구간 & 볼륨 설정
        </h3>

        {/* 악기 선택 (드롭다운) */}
        <div className="mb-3">
          <label className="text-xs text-dark-400 mb-1 block">악기</label>
          <select
            value={selectedInstrument}
            onChange={e => setSelectedInstrument(e.target.value)}
            className="w-full bg-dark-900 border border-dark-600 rounded-lg px-3 py-2
                       text-sm text-white focus:outline-none focus:border-orange-500"
          >
            <option value="">선택하세요</option>
            {availableStems.map(stem => (
              <option key={stem} value={stem}>
                {STEM_CONFIG[stem]?.label || stem} ({STEM_CONFIG[stem]?.en || stem})
              </option>
            ))}
          </select>
        </div>

        {/* 구간 슬라이더 */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs text-dark-400 mb-1 block">
              시작 <span className="text-orange-400">{formatTime(startSec)}</span>
            </label>
            <input
              type="range"
              min="0"
              max={maxDuration}
              step="1"
              value={startSec}
              onChange={e => {
                const v = Number(e.target.value);
                setStartSec(v);
                if (v >= endSec) setEndSec(Math.min(v + 1, maxDuration));
              }}
              className="time-slider w-full"
              style={{
                background: `linear-gradient(to right, #f97316 ${(startSec / maxDuration) * 100}%, #374151 ${(startSec / maxDuration) * 100}%)`
              }}
            />
          </div>
          <div>
            <label className="text-xs text-dark-400 mb-1 block">
              끝 <span className="text-orange-400">{formatTime(endSec)}</span>
            </label>
            <input
              type="range"
              min="0"
              max={maxDuration}
              step="1"
              value={endSec}
              onChange={e => {
                const v = Number(e.target.value);
                setEndSec(v);
                if (v <= startSec) setStartSec(Math.max(v - 1, 0));
              }}
              className="time-slider w-full"
              style={{
                background: `linear-gradient(to right, #f97316 ${(endSec / maxDuration) * 100}%, #374151 ${(endSec / maxDuration) * 100}%)`
              }}
            />
          </div>
        </div>

        <div className="text-xs text-dark-500 mb-3">
          선택 구간: {formatTime(startSec)} ~ {formatTime(endSec)} ({(endSec - startSec).toFixed(0)}초)
        </div>

        {/* 볼륨 프리셋 */}
        <div className="mb-3">
          <label className="text-xs text-dark-400 mb-1 block">볼륨 조절</label>
          <div className="grid grid-cols-3 gap-1">
            {VOLUME_PRESETS.map(p => (
              <button
                key={p.db}
                onClick={() => setVolumePreset(p.db)}
                className={`px-1.5 py-1 rounded text-[11px] font-medium transition-all
                  ${volumePreset === p.db
                    ? p.db <= -100
                      ? 'bg-red-500/30 text-red-400 ring-1 ring-red-500/50'
                      : p.db > 0
                        ? 'bg-green-500/30 text-green-400 ring-1 ring-green-500/50'
                        : p.db < 0
                          ? 'bg-yellow-500/30 text-yellow-400 ring-1 ring-yellow-500/50'
                          : 'bg-dark-600 text-white ring-1 ring-dark-400'
                    : 'bg-dark-900 text-dark-400 hover:bg-dark-700'
                  }`}
              >
                {p.db <= -100 ? <VolumeX className="w-3 h-3 inline mr-0.5" /> : null}
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* 프롬프트에 추가 버튼 */}
        <button
          onClick={addToPrompt}
          disabled={!selectedInstrument}
          className="w-full py-2 bg-dark-700 hover:bg-dark-600 text-white text-sm 
                     rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ➕ 프롬프트에 추가
        </button>
      </div>

      {/* 프롬프트 자유 입력 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-dark-400 uppercase tracking-wider">
            프롬프트 입력
          </h3>
          <div className="flex items-center gap-1">
            <button
              onClick={savePromptToHistory}
              disabled={!prompt.trim() || savingPrompt}
              className="p-1.5 rounded hover:bg-dark-700 text-dark-500 hover:text-green-400
                         transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="프롬프트 저장"
            >
              <Save className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`p-1.5 rounded hover:bg-dark-700 transition-colors
                         ${showHistory ? 'text-orange-400 bg-dark-700' : 'text-dark-500 hover:text-orange-400'}`}
              title="프롬프트 히스토리"
            >
              <History className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={clearPrompt}
              disabled={!prompt.trim()}
              className="p-1.5 rounded hover:bg-dark-700 text-dark-500 hover:text-red-400
                         transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="프롬프트 전체 삭제"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 히스토리 패널 */}
        {showHistory && (
          <div className="mb-3 bg-dark-800/80 rounded-lg border border-dark-600 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-dark-700">
              <span className="text-xs font-semibold text-dark-300 flex items-center gap-1.5">
                <Clock className="w-3 h-3" />
                프롬프트 히스토리
              </span>
              <button onClick={() => setShowHistory(false)} className="text-dark-500 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto">
              {historyItems.length === 0 ? (
                <p className="text-xs text-dark-500 p-3 text-center">저장된 프롬프트가 없습니다</p>
              ) : (
                historyItems.map(item => (
                  <div
                    key={item.filename}
                    onClick={() => loadPromptFromHistory(item)}
                    className="px-3 py-2 hover:bg-dark-700/60 cursor-pointer border-b border-dark-700/50
                               last:border-b-0 transition-colors group"
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[10px] text-dark-500 font-mono">{item.filename}</span>
                      <button
                        onClick={(e) => deleteHistoryItem(item.filename, e)}
                        className="opacity-0 group-hover:opacity-100 text-dark-500 hover:text-red-400
                                   transition-all p-0.5"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <p className="text-xs text-dark-300 line-clamp-2 leading-relaxed">
                      {item.prompt}
                    </p>
                    <span className="text-[9px] text-dark-600 mt-0.5 block">{item.created_at}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder={"예시:\n전주 드럼 키워줘\n30초~40초 피아노 작게\n기타 음소거\n후주 보컬 키워줘"}
          rows={5}
          className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2
                     text-sm text-white placeholder-dark-600 resize-none
                     focus:outline-none focus:border-orange-500"
        />
        <p className="text-[10px] text-dark-600 mt-1">
          인식 가능: 보컬, 드럼, 베이스, 기타, 피아노 | 구간: 전주, 후주, X초~Y초 | 볼륨: 키워, 작게, 음소거
        </p>
      </div>

      {/* 실행 버튼들 */}
      <div className="flex gap-2">
        <button
          onClick={handleParsePreview}
          disabled={!prompt.trim()}
          className="flex-1 py-2.5 bg-dark-700 hover:bg-dark-600 text-white text-sm
                     rounded-lg transition-colors disabled:opacity-40"
        >
          미리보기
        </button>
        <button
          onClick={handleMix}
          disabled={!prompt.trim() || isMixing}
          className="flex-[2] py-2.5 bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold
                     rounded-lg transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
        >
          {isMixing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              AI 믹싱 실행 중...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" fill="white" />
              믹싱 실행
            </>
          )}
        </button>
      </div>

      {/* 믹싱 진행율 */}
      {isMixing && mixProgress > 0 && (
        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-dark-400">AI 믹싱 실행 중...</span>
            <span className="text-orange-400">{mixProgress}%</span>
          </div>
          <div className="h-1 bg-dark-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-orange-500 to-orange-400 transition-all duration-300"
              style={{ width: `${mixProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* 파싱 결과 미리보기 */}
      {parsedCommands.length > 0 && (
        <div className="bg-dark-800/50 rounded-lg p-3 border border-dark-700">
          <h4 className="text-xs font-semibold text-dark-400 mb-2">파싱된 명령 ({parsedCommands.length}개)</h4>
          <div className="space-y-1">
            {parsedCommands.map((cmd, i) => {
              const cfg = STEM_CONFIG[cmd.instrument];
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium
                    ${cmd.volume_db <= -100 ? 'bg-red-500/20 text-red-400'
                      : cmd.volume_db > 0 ? 'bg-green-500/20 text-green-400'
                      : cmd.volume_db < 0 ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-dark-700 text-dark-300'}`}>
                    {cmd.volume_db <= -100 ? 'MUTE' : `${cmd.volume_db > 0 ? '+' : ''}${cmd.volume_db}dB`}
                  </span>
                  <span className="text-white">{cfg?.label || cmd.instrument}</span>
                  <span className="text-dark-500">
                    {formatTime(cmd.start_sec)}~{formatTime(cmd.end_sec)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 믹싱 로그 */}
      {mixLog && (
        <div className="bg-dark-900 rounded-lg p-3 border border-dark-700">
          <pre className="text-xs text-dark-300 whitespace-pre-wrap font-mono">{mixLog}</pre>
        </div>
      )}

      {/* 믹싱 결과 플레이어 */}
      {mixResult && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-dark-400 uppercase tracking-wider">
              믹싱 결과
            </h3>
            <button
              onClick={() => onExpandMixResult && onExpandMixResult({
                url: mixResult,
                title: 'Mixed Result',
                duration,
                jobId,
                mixId,
              })}
              className="p-1 rounded hover:bg-dark-700 text-dark-500 hover:text-orange-400 transition-colors"
              title="중앙 패널에 확대 표시"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
          <AudioPlayer
            url={mixResult}
            title="Mixed Result"
            duration={duration}
            color="orange"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => mixId && jobId && window.open(`/api/download-mix/${jobId}/${mixId}`, '_blank')}
              className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 text-white text-xs
                         rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              다운로드
            </button>
            <button
              onClick={() => onAddToLibrary && onAddToLibrary(mixId)}
              className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 text-white text-xs
                         rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Library 추가
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTime(seconds) {
  if (!seconds || !isFinite(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default MixingPanel;
