import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';

function AudioPlayer({ url, title, duration: propDuration, color = 'lukus', onTimeUpdate: onTimeUpdateCb, externalAudioRef, children }) {
  const audioRef = useRef(null);

  const setAudioRef = useCallback((el) => {
    audioRef.current = el;
    if (typeof externalAudioRef === 'function') externalAudioRef(el);
    else if (externalAudioRef) externalAudioRef.current = el;
  }, [externalAudioRef]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(propDuration || 0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showVolumeSlider, setShowVolumeSlider] = useState(false);
  const volumeTimerRef = useRef(null);

  useEffect(() => {
    if (propDuration) setDuration(propDuration);
  }, [propDuration]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      if (onTimeUpdateCb) onTimeUpdateCb(audio.currentTime);
    };
    const handleEnded = () => { setIsPlaying(false); setCurrentTime(0); };
    const handleLoadedMetadata = () => {
      if (audio.duration && isFinite(audio.duration)) {
        setDuration(audio.duration);
      }
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [url]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) { audio.pause(); } else { audio.play(); }
    setIsPlaying(!isPlaying);
  };

  const toggleMute = () => {
    const audio = audioRef.current;
    if (!audio) return;
    const newMuted = !isMuted;
    audio.muted = newMuted;
    setIsMuted(newMuted);
  };

  const handleTimeSeek = (e) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    const newTime = parseFloat(e.target.value);
    audio.currentTime = newTime;
    setCurrentTime(newTime);
    if (onTimeUpdateCb) onTimeUpdateCb(newTime);
  };

  const handleVolumeChange = (e) => {
    const audio = audioRef.current;
    if (!audio) return;
    const newVol = parseFloat(e.target.value);
    audio.volume = newVol;
    setVolume(newVol);
    if (newVol === 0) { setIsMuted(true); audio.muted = true; }
    else if (isMuted) { setIsMuted(false); audio.muted = false; }
  };

  const handleVolumeEnter = useCallback(() => {
    if (volumeTimerRef.current) clearTimeout(volumeTimerRef.current);
    setShowVolumeSlider(true);
  }, []);

  const handleVolumeLeave = useCallback(() => {
    volumeTimerRef.current = setTimeout(() => setShowVolumeSlider(false), 400);
  }, []);

  const formatTime = (seconds) => {
    if (!seconds || !isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progress = duration ? (currentTime / duration) * 100 : 0;

  const colorMap = {
    lukus: { bg: 'bg-lukus-500', track: '#22c55e', thumb: '#16a34a' },
    green: { bg: 'bg-green-500', track: '#22c55e', thumb: '#16a34a' },
    orange: { bg: 'bg-orange-500', track: '#f97316', thumb: '#ea580c' },
    purple: { bg: 'bg-purple-500', track: '#8b5cf6', thumb: '#7c3aed' },
    cyan: { bg: 'bg-cyan-500', track: '#06b6d4', thumb: '#0891b2' },
    pink: { bg: 'bg-pink-500', track: '#ec4899', thumb: '#db2777' },
    slate: { bg: 'bg-slate-500', track: '#64748b', thumb: '#475569' },
  };
  const c = colorMap[color] || colorMap.lukus;

  const sliderStyle = {
    background: `linear-gradient(to right, ${c.track} ${progress}%, #374151 ${progress}%)`,
  };

  const volumePercent = isMuted ? 0 : volume * 100;
  const volumeSliderStyle = {
    background: `linear-gradient(to top, ${c.track} ${volumePercent}%, #374151 ${volumePercent}%)`,
  };

  return (
    <div className="audio-player">
      <audio ref={setAudioRef} src={url} preload="metadata" />

      <div className="grid gap-x-3" style={{ gridTemplateColumns: '40px 1fr auto' }}>
        {/* 재생 버튼 */}
        <button
          onClick={togglePlay}
          className={`w-10 h-10 rounded-full flex items-center justify-center self-center
                     ${c.bg} hover:opacity-90 transition-opacity`}
        >
          {isPlaying ? (
            <Pause className="w-5 h-5 text-white" fill="white" />
          ) : (
            <Play className="w-5 h-5 text-white ml-0.5" fill="white" />
          )}
        </button>

        {/* 타이틀 + 타임 슬라이더 */}
        <div className="min-w-0">
          <p className="text-sm font-medium text-white truncate mb-1">{title}</p>

          <input
            type="range"
            min="0"
            max={duration || 0}
            step="0.1"
            value={currentTime}
            onChange={handleTimeSeek}
            className="time-slider w-full"
            style={sliderStyle}
          />

          <div className="flex justify-between mt-0.5">
            <span className="text-xs text-dark-500">{formatTime(currentTime)}</span>
            <span className="text-xs text-dark-500">{formatTime(duration)}</span>
          </div>
        </div>

        {/* 볼륨 영역 */}
        <div
          className="relative self-center"
          onMouseEnter={handleVolumeEnter}
          onMouseLeave={handleVolumeLeave}
        >
          {showVolumeSlider && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                            bg-dark-800 border border-dark-600 rounded-lg p-2 shadow-xl z-50
                            flex flex-col items-center gap-1">
              <span className="text-[10px] text-dark-400 mb-1">
                {Math.round(volumePercent)}%
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="volume-slider-vertical"
                style={volumeSliderStyle}
              />
            </div>
          )}

          <button
            onClick={toggleMute}
            className="text-dark-400 hover:text-white transition-colors p-1"
          >
            {isMuted || volume === 0 ? (
              <VolumeX className="w-5 h-5" />
            ) : (
              <Volume2 className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* 타임라인 정렬된 하위 콘텐츠 (스펙트로그램 등) */}
        {children && (
          <div style={{ gridColumn: 2 }}>{children}</div>
        )}
      </div>
    </div>
  );
}

export default AudioPlayer;
