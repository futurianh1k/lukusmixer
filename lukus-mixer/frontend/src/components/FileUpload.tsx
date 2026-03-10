import React, { useCallback } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Upload, X, FileAudio } from 'lucide-react';
import type { FileUploadProps } from '../types/api';

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '0 MB';
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

function FileUpload({ onUpload, uploadedFile, onRemove }: FileUploadProps): React.ReactElement {
  const onDrop = useCallback((acceptedFiles: File[], _rejections: FileRejection[]) => {
    if (acceptedFiles.length > 0) {
      onUpload(acceptedFiles[0]);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.mp3', '.wav', '.flac', '.ogg', '.m4a']
    },
    maxFiles: 1
  });

  if (uploadedFile) {
    return (
      <div className="bg-dark-800 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-lukus-500/20 rounded-lg flex items-center justify-center">
            <FileAudio className="w-6 h-6 text-lukus-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {uploadedFile.filename}
            </p>
            <p className="text-xs text-dark-400">
              {formatDuration(uploadedFile.duration)} • {formatFileSize(uploadedFile.size)}
            </p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove?.(); }}
            className="text-dark-500 hover:text-red-400 transition-colors"
            title="파일 제거"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`dropzone ${isDragActive ? 'active' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors
          ${isDragActive ? 'bg-lukus-500/20' : 'bg-dark-800'}`}>
          <Upload className={`w-6 h-6 ${isDragActive ? 'text-lukus-400' : 'text-dark-400'}`} />
        </div>
        <div className="text-center">
          <p className="text-sm text-white mb-1">
            {isDragActive ? '파일을 놓으세요' : '파일을 드래그하거나 클릭'}
          </p>
          <p className="text-xs text-dark-500">
            MP3, WAV, FLAC, OGG, M4A
          </p>
        </div>
      </div>
    </div>
  );
}

export default FileUpload;
