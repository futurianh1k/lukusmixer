/**
 * useJobWebSocket — WebSocket 기반 작업 상태 실시간 구독 훅
 *
 * 참고: https://developer.mozilla.org/ko/docs/Web/API/WebSocket
 *
 * WS 연결이 실패하면 자동으로 HTTP 폴링으로 폴백.
 * 서버가 WS를 지원하지 않는 환경(일부 프록시/CDN)에서도 안전하게 동작.
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import axios from 'axios';
import type { UseJobWebSocketCallbacks, UseJobWebSocketReturn, WsJobUpdate } from '../types/api';

const API_BASE = '/api';
const RECONNECT_MAX = 3;
const POLL_INTERVAL_MS = 1500;

export default function useJobWebSocket(
  jobId: string | null,
  { onUpdate, onComplete, onFailed }: UseJobWebSocketCallbacks
): UseJobWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const [usingFallback, setUsingFallback] = useState(false);

  const handleMessage = useCallback((data: WsJobUpdate) => {
    if (data.type === 'job_update') {
      onUpdate?.(data);
      if (data.status === 'completed') {
        onComplete?.(data);
      } else if (data.status === 'failed') {
        onFailed?.(data);
      }
    }
  }, [onUpdate, onComplete, onFailed]);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      setUsingFallback(true);
      pollTimer = setInterval(async () => {
        if (cancelled) return;
        try {
          const res = await axios.get(`${API_BASE}/job/${jobId}`);
          handleMessage({ type: 'job_update', ...res.data });
          if (res.data.status === 'completed' || res.data.status === 'failed') {
            if (pollTimer) clearInterval(pollTimer);
          }
        } catch (err) {
          console.error('폴링 오류:', err);
        }
      }, POLL_INTERVAL_MS);
    };

    const connect = () => {
      if (cancelled) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/job/${jobId}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WsJobUpdate;
          handleMessage(data);
          if (data.status === 'completed' || data.status === 'failed') {
            ws.close();
          }
        } catch (err) {
          console.error('WS 메시지 파싱 오류:', err);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (cancelled) return;
        retriesRef.current += 1;
        if (retriesRef.current >= RECONNECT_MAX) {
          console.warn('WebSocket 재연결 실패, HTTP 폴링으로 전환');
          startPolling();
        } else {
          setTimeout(connect, 1000 * retriesRef.current);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [jobId, handleMessage]);

  return { usingFallback };
}
