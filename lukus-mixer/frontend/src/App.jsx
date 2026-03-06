import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import FileUpload from './components/FileUpload';
import StemSelector from './components/StemSelector';
import ResultPanel from './components/ResultPanel';
import MixingPanel from './components/MixingPanel';
import AudioPlayer from './components/AudioPlayer';
import axios from 'axios';

const API_BASE = '/api';

const MODELS = [
  { id: 'htdemucs', name: '4 스템 (기본)', stems: ['vocals', 'drums', 'bass', 'other'] },
  { id: 'htdemucs_ft', name: '4 스템 (고품질)', stems: ['vocals', 'drums', 'bass', 'other'] },
  { id: 'htdemucs_6s', name: '6 스템', stems: ['vocals', 'drums', 'bass', 'guitar', 'piano', 'other'] },
];

function App() {
  // 상태
  const [uploadedFile, setUploadedFile] = useState(null);
  const [selectedStems, setSelectedStems] = useState(['vocals', 'drums', 'bass', 'other']);
  const [selectedModel, setSelectedModel] = useState('htdemucs');
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // 모델에 따른 스템 업데이트
  useEffect(() => {
    const model = MODELS.find(m => m.id === selectedModel);
    if (model) {
      setSelectedStems(model.stems);
    }
  }, [selectedModel]);

  // 파일 업로드 핸들러
  const handleFileUpload = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_BASE}/upload`, formData, {
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
    } catch (error) {
      console.error('업로드 오류:', error);
      alert('파일 업로드에 실패했습니다.');
    }
  };

  // STEM 분리 시작
  const handleSplit = async () => {
    if (!uploadedFile) return;

    setIsProcessing(true);
    setResults(null);

    try {
      const response = await axios.post(`${API_BASE}/split/${uploadedFile.file_id}`, {
        stems: selectedStems,
        model: selectedModel
      });
      
      setJobId(response.data.job_id);
    } catch (error) {
      console.error('분리 시작 오류:', error);
      alert('STEM 분리 시작에 실패했습니다.');
      setIsProcessing(false);
    }
  };

  // 작업 상태 폴링
  useEffect(() => {
    if (!jobId) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_BASE}/job/${jobId}`);
        setJobStatus(response.data);

        if (response.data.status === 'completed') {
          setResults(response.data.result);
          setIsProcessing(false);
          clearInterval(pollInterval);
        } else if (response.data.status === 'failed') {
          setIsProcessing(false);
          clearInterval(pollInterval);
          alert(`오류: ${response.data.message}`);
        }
      } catch (error) {
        console.error('상태 조회 오류:', error);
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [jobId]);

  // 스템 다운로드
  const handleDownload = (stemName) => {
    if (!jobId) return;
    window.open(`${API_BASE}/download/${jobId}/${stemName}`, '_blank');
  };

  // ZIP 전체 다운로드
  const handleDownloadAll = () => {
    if (!jobId) return;
    window.open(`${API_BASE}/download-all/${jobId}`, '_blank');
  };

  // 라이브러리에 추가
  const handleAddToLibrary = async (mixId) => {
    if (!jobId) return;
    try {
      const res = await axios.post(`${API_BASE}/library/add`, {
        job_id: jobId,
        mix_id: mixId || null,
      });
      alert(res.data.message);
    } catch (err) {
      alert('라이브러리 추가 실패: ' + (err.response?.data?.detail || err.message));
    }
  };

  // 현재 모델의 사용 가능한 스템
  const availableStems = MODELS.find(m => m.id === selectedModel)?.stems || [];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 왼쪽 패널 - 업로드 & 설정 */}
        <div className="w-[400px] border-r border-dark-700 flex flex-col overflow-y-auto">
          <div className="p-6">
            <h1 className="text-2xl font-bold mb-6">Stem Splitter</h1>
            <p className="text-dark-400 text-sm mb-8">
              음악 파일에서 악기와 보컬을 분리합니다.
            </p>

            {/* 파일 업로드 */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-dark-300 mb-3">Uploaded File</h3>
              <FileUpload 
                onUpload={handleFileUpload} 
                uploadedFile={uploadedFile}
              />
            </div>

            {/* 업로드된 파일 미리듣기 */}
            {uploadedFile && (
              <div className="mb-6">
                <AudioPlayer 
                  url={uploadedFile.url} 
                  title={uploadedFile.filename}
                  duration={uploadedFile.duration}
                />
              </div>
            )}

            {/* 모델 선택 */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-dark-300 mb-3">Model</h3>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-dark-800 border border-dark-600 rounded-lg px-4 py-3 
                           text-white focus:outline-none focus:border-lukus-500"
              >
                {MODELS.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            </div>

            {/* 스템 선택 */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-dark-300 mb-3">Select Stems</h3>
              <StemSelector
                availableStems={availableStems}
                selectedStems={selectedStems}
                onChange={setSelectedStems}
              />
            </div>

            {/* 진행 상태 + 로그 */}
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

            {/* 처리 로그 */}
            {jobStatus?.logs && jobStatus.logs.length > 0 && (
              <div className="mb-6 bg-dark-900 rounded-lg p-3 border border-dark-700 max-h-40 overflow-y-auto">
                <h4 className="text-[10px] text-dark-500 uppercase tracking-wider mb-1.5">Log</h4>
                {jobStatus.logs.map((log, i) => (
                  <div key={i} className="text-[11px] text-dark-400 font-mono leading-relaxed">{log}</div>
                ))}
              </div>
            )}

            {/* 분리 버튼 */}
            <button
              onClick={handleSplit}
              disabled={!uploadedFile || isProcessing}
              className="btn-primary w-full"
            >
              {isProcessing ? '처리 중...' : 'Split Stems'}
            </button>
          </div>
        </div>

        {/* 중앙 패널 - 결과 (스펙트로그램 + 오디오) */}
        <div className="flex-1 bg-dark-900/50 overflow-y-auto">
          <ResultPanel 
            results={results}
            jobId={jobId}
            uploadedFile={uploadedFile}
            onDownload={handleDownload}
            onDownloadAll={handleDownloadAll}
            onAddToLibrary={handleAddToLibrary}
            selectedStems={selectedStems}
          />
        </div>

        {/* 오른쪽 패널 - 프롬프트 믹싱 */}
        <div className="w-[380px] border-l border-dark-700 bg-dark-950 overflow-y-auto">
          <MixingPanel
            results={results}
            jobId={jobId}
            duration={uploadedFile?.duration}
            onAddToLibrary={handleAddToLibrary}
            originalFilename={uploadedFile?.filename}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
