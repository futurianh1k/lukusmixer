import React, { Component, ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { ErrorBoundaryProps, ErrorBoundaryState } from '../types/api';

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error(`[ErrorBoundary] ${this.props.name || 'Unknown'}:`, error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 h-full min-h-[200px]">
          <div className="w-14 h-14 bg-red-500/10 rounded-xl flex items-center justify-center mb-4">
            <AlertTriangle className="w-7 h-7 text-red-400" />
          </div>
          <h3 className="text-sm font-semibold text-dark-300 mb-1">
            {this.props.name ? `${this.props.name}에서 오류 발생` : '오류가 발생했습니다'}
          </h3>
          <p className="text-xs text-dark-500 mb-4 text-center max-w-xs">
            이 영역에서 문제가 발생했습니다. 다시 시도해주세요.
          </p>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-4 py-2 bg-dark-700 hover:bg-dark-600
                       text-sm text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            다시 시도
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
