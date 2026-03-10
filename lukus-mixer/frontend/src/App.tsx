import React, { useState, useEffect, useCallback, useRef } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import ErrorBoundary from './components/ErrorBoundary';
import FileUpload from './components/FileUpload';
import StemSelector from './components/StemSelector';
import ResultPanel from './components/ResultPanel';
import MixingPanel from './components/MixingPanel';
import AudioPlayer from './components/AudioPlayer';
import useJobWebSocket from './hooks/useJobWebSocket';
import axios from 'axios';
import type { ModelInfo, UploadedFile, StemResult, JobStatus, ExpandedMix, WsJobUpdate } from './types/api';

const API_BASE = '/api';

interface FallbackModel {
  id: string;
  name: string;
  stems: string[];
  engine: string;
  description: string;
}

const FALLBACK_MODELS: FallbackModel[] = [
  { id: 'htdemucs', name: '4 스템 (기본)', stems: ['vocals', 'drums', 'bass', 'other'], engine: 'demucs', description: 'Demucs — 빠른 속도' },
];

type TabId = 'settings' | 'results' | 'mixing';

interface Tab {
  id: TabId;
  label: string;
}

const TABS: Tab[] = [
  { id: 'settings', label: '설정' },
  { id: 'results',  label: '결과' },
  { id: 'mixing',   label: '믹싱' },
];

function App(): React.ReactElement {
  const [models, setModels] = useState<FallbackModel[]>(FALLBACK_MODELS);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [selectedStems, setSelectedStems] = useState<string[]>(['vocals', 'drums', 'bass', 'other']);
  const [selectedModel, setSelectedModel] = useState('htdemucs');
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<WsJobUpdate | null>(null);
  const [results, setResults] = useState<Record<string, StemResult> | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [promptAppend, setPromptAppend] = useState<{ text: string; id: number } | null>(null);
  const [expandedMix, setExpandedMix] = useState<ExpandedMix | null>(null);
  const appendIdRef = useRef(0);

  const handleAppendPrompt = useCallback((text: string) => {
    appendIdRef.current += 1;
    setPromptAppend({ text, id: appendIdRef.current });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get<{ models: ModelInfo[] }>(`${API_BASE}/system`);
        const serverModels = (res.data.models || []).map(m => ({
          id: m.id,
          name: m.name,
          stems: m.stems,
          engine: m.engine || 'demucs',
          description: m.description || '',
        }));
        if (serverModels.length > 0) {
          setModels(serverModels);
        }
      } catch (err) {
        console.error('모델 목록 로드 실패, 폴백 사용:', err);
      }
    })();
  }, []);

  useEffect(() => {
    const model = models.find(m => m.id === selectedModel);
    if (model) {
      setSelectedStems(model.stems);
    }
  }, [selectedModel, models]);

  const handleRemoveFile = useCallback(() => {
    if (uploadedFile?.url) {
      URL.revokeObjectURL(uploadedFile.url);
    }
    setUploadedFile(null);
    setResults(null);
    setJobId(null);
    setJobStatus(null);
    setIsProcessing(false);
    setExpandedMix(null);
  }, [uploadedFile]);

  const handleFileUpload = async (file: File): Promise<void> => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post<{ file_id: string; filename: string; duration: number; size: number }>(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setUploadedFile({
        ...response.data,
        file: file,
        url: URL.createObjectURL(file)
      });
      setResults(null);
      setJobId(null);
      setJobStatus(null);
    } catch (error: any) {
      console.error('업로드 오류:', error);
      toast.error(error.response?.data?.detail || '파일 업로드에 실패했습니다.');
    }
  };

  const handleSplit = async (): Promise<void> => {
    if (!uploadedFile) return;

    setIsProcessing(true);
    setResults(null);

    try {
      const response = await axios.post<{ job_id: string; status: string }>(`${API_BASE}/split/${uploadedFile.file_id}`, {
        stems: selectedStems,
        model: selectedModel
      });
      
      setJobId(response.data.job_id);
    } catch (error: any) {
      console.error('분리 시작 오류:', error);
      toast.error(error.response?.data?.detail || 'STEM 분리 시작에 실패했습니다.');
      setIsProcessing(false);
    }
  };

  useJobWebSocket(isProcessing ? jobId : null, {
    onUpdate: useCallback((data: WsJobUpdate) => {
      setJobStatus(data);
    }, []),
    onComplete: useCallback((data: WsJobUpdate) => {
      setResults(data.result);
      setIsProcessing(false);
      toast.success('STEM 분리가 완료되었습니다!');
    }, []),
    onFailed: useCallback((data: WsJobUpdate) => {
      setIsProcessing(false);
      toast.error(data.message || '처리 중 오류가 발생했습니다.');
    }, []),
  });

  const handleDownload = (stemName: string): void => {
    if (!jobId) return;
    window.open(`${API_BASE}/download/${jobId}/${stemName}`, '_blank');
  };

  const handleDownloadAll = (): void => {
    if (!jobId) return;
    window.open(`${API_BASE}/download-all/${jobId}`, '_blank');
  };

  const handleAddToLibrary = async (mixId?: string): Promise<void> => {
    if (!jobId) return;
    try {
      const res = await axios.post<{ message: string }>(`${API_BASE}/library/add`, {
        job_id: jobId,
        mix_id: mixId || null,
      });
      toast.success(res.data.message);
    } catch (err: any) {
      toast.error('라이브러리 추가 실패: ' + (err.response?.data?.detail || err.message));
    }
  };

  const availableStems = models.find(m => m.id === selectedModel)?.stems || [];

  const [mobileTab, setMobileTab] = useState<TabId>('settings');

  const settingsContent = (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Stem Splitter</h1>
      <p className="text-dark-400 text-sm mb-8">
        음악 파일에서 악기와 보컬을 분리합니다.
      </p>

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-dark-300 mb-3">Uploaded File</h3>
        <FileUpload 
          onUpload={handleFileUpload} 
          uploadedFile={uploadedFile}
          onRemove={handleRemoveFile}
        />
      </div>

      {uploadedFile && (
        <div className="mb-6">
          <AudioPlayer 
            url={uploadedFile.url} 
            title={uploadedFile.filename}
            duration={uploadedFile.duration}
          />
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-dark-300 mb-3">Model</h3>
        <div className="space-y-1.5">
          {models.map(m => {
            const isSelected = selectedModel === m.id;
            const isPro = m.engine === 'chained' || m.engine === 'chained_10s';
            const is10s = m.engine === 'chained_10s';
            return (
              <button
                key={m.id}
                onClick={() => setSelectedModel(m.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all
                  ${isSelected
                    ? isPro
                      ? is10s
                        ? 'border-red-500/70 bg-red-500/10 ring-1 ring-red-500/30'
                        : 'border-orange-500/70 bg-orange-500/10 ring-1 ring-orange-500/30'
                      : 'border-lukus-500/70 bg-lukus-500/10 ring-1 ring-lukus-500/30'
                    : 'border-dark-700 bg-dark-800/50 hover:border-dark-500'
                  }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${isSelected ? 'text-white' : 'text-dark-300'}`}>
                    {m.name}
                  </span>
                  {isPro && (
                    <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5
                                   rounded border ${is10s
                                     ? 'bg-red-500/20 text-red-400 border-red-500/30'
                                     : 'bg-orange-500/20 text-orange-400 border-orange-500/30'}`}>
                      {is10s ? 'MAX' : 'PRO'}
                    </span>
                  )}
                </div>
                <p className={`text-[11px] mt-0.5 ${isSelected ? 'text-dark-400' : 'text-dark-600'}`}>
                  {m.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-sm font-semibold text-dark-300 mb-3">Select Stems</h3>
        <StemSelector
          availableStems={availableStems}
          selectedStems={selectedStems}
          onChange={setSelectedStems}
        />
      </div>

      {jobStatus && isProcessing && (
        <div className="mb-6">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-dark-400">{jobStatus.message}</span>
            <span className="text-lukus-400">{jobStatus.progress}%</span>
          </div>
          <div className="progress-bar">
            <div 
              className="progress-bar-fill" 
              style={{ width: `${jobStatus.progress}%` }}
            />
          </div>
        </div>
      )}

      {jobStatus?.logs && jobStatus.logs.length > 0 && (
        <div className="mb-6 bg-dark-900 rounded-lg p-3 border border-dark-700 max-h-40 overflow-y-auto">
          <h4 className="text-[10px] text-dark-500 uppercase tracking-wider mb-1.5">Log</h4>
          {jobStatus.logs.map((log, i) => (
            <div key={i} className="text-[11px] text-dark-400 font-mono leading-relaxed">{log}</div>
          ))}
        </div>
      )}

      <button
        onClick={handleSplit}
        disabled={!uploadedFile || isProcessing}
        className="btn-primary w-full"
      >
        {isProcessing ? '처리 중...' : 'Split Stems'}
      </button>
    </div>
  );

  const resultsContent = (
    <ErrorBoundary name="결과 패널">
      <ResultPanel 
        results={results}
        jobId={jobId}
        uploadedFile={uploadedFile}
        onDownload={handleDownload}
        onDownloadAll={handleDownloadAll}
        onAddToLibrary={handleAddToLibrary}
        selectedStems={selectedStems}
        onAppendPrompt={handleAppendPrompt}
        expandedMix={expandedMix}
        onCloseExpandedMix={() => setExpandedMix(null)}
      />
    </ErrorBoundary>
  );

  const mixingContent = (
    <ErrorBoundary name="믹싱 패널">
      <MixingPanel
        results={results}
        jobId={jobId}
        duration={uploadedFile?.duration}
        onAddToLibrary={handleAddToLibrary}
        originalFilename={uploadedFile?.filename}
        externalPromptAppend={promptAppend}
        onExpandMixResult={setExpandedMix}
      />
    </ErrorBoundary>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155' },
          success: { iconTheme: { primary: '#22c55e', secondary: '#0f172a' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#0f172a' }, duration: 6000 },
        }}
      />

      <div className="hidden lg:block">
        <Sidebar />
      </div>

      <div className="hidden lg:flex flex-1 overflow-hidden">
        <div className="w-[400px] border-r border-dark-700 flex flex-col overflow-y-auto">
          {settingsContent}
        </div>
        <div className="flex-1 bg-dark-900/50 overflow-y-auto">
          {resultsContent}
        </div>
        <div className="w-[380px] border-l border-dark-700 bg-dark-950 overflow-y-auto">
          {mixingContent}
        </div>
      </div>

      <div className="flex lg:hidden flex-1 flex-col overflow-hidden">
        <div className="flex border-b border-dark-700 bg-dark-900 shrink-0">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setMobileTab(tab.id)}
              className={`flex-1 py-3 text-sm font-medium transition-colors relative
                ${mobileTab === tab.id
                  ? 'text-orange-400'
                  : 'text-dark-500 hover:text-dark-300'
                }`}
            >
              {tab.label}
              {mobileTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-orange-500" />
              )}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto">
          {mobileTab === 'settings' && settingsContent}
          {mobileTab === 'results' && (
            <div className="bg-dark-900/50 min-h-full">{resultsContent}</div>
          )}
          {mobileTab === 'mixing' && (
            <div className="bg-dark-950 min-h-full">{mixingContent}</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
