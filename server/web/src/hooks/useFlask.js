import { useState, useEffect, useCallback, useRef } from 'react';

const FLASK_URL = 'http://localhost:5000';

const initialState = {
  fsm: 'IDLE',
  ear: 0.32,
  gaze: { cx: 640, cy: 400, rx: 0, ry: 0 },
  dwell: 0,
  robot: { x: 135, y: -82, z: 200, rx: 0, ry: 0, rz: 0 },
  gripper: 'open',
  gaze_enabled: true,
};

export function useFlask() {
  const [state, setState] = useState(initialState);
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState([]);
  const esRef = useRef(null);

  const addLog = useCallback((type, msg) => {
    const ts = new Date().toTimeString().slice(0, 8);
    setLogs(prev => [...prev.slice(-200), { type, msg, ts }]);
  }, []);

  // SSE 연결
  useEffect(() => {
    function connect() {
      const es = new EventSource(`${FLASK_URL}/stream`);
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        addLog('ok', 'Flask SSE 연결됨');
      };

      es.onmessage = (e) => {
        try { setState(JSON.parse(e.data)); } catch {}
      };

      es.onerror = () => {
        setConnected(false);
        addLog('err', 'Flask 연결 끊김 — 3초 후 재시도');
        es.close();
        setTimeout(connect, 3000);
      };
    }

    // Flask 있는지 먼저 확인
    fetch(`${FLASK_URL}/api/state`, { signal: AbortSignal.timeout(1500) })
      .then(connect)
      .catch(() => {
        addLog('warn', 'Flask 없음 — 시뮬레이션 모드');
        startSimulation(setState, addLog);
      });

    return () => esRef.current?.close();
  }, [addLog]);

  // Flask API 호출
  const apiPost = useCallback(async (path, body) => {
    try {
      await fetch(`${FLASK_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) {
      addLog('err', `API 오류: ${path}`);
    }
  }, [addLog]);

  const triggerStop  = () => { apiPost('/api/fsm', { state: 'ESTOP' }); addLog('err', '긴급정지'); };
  const toggleGaze   = () => { apiPost('/api/gaze_toggle', {}); addLog('info', '시선 제어 토글'); };
  const setGripper   = (open) => { apiPost('/api/gripper', { state: open ? 'open' : 'closed' }); };

  return { state, connected, logs, setLogs, addLog, triggerStop, toggleGaze, setGripper };
}

// 시뮬레이션 (Flask 없을 때)
function startSimulation(setState, addLog) {
  let earV = 0.32, gx = 640, gy = 400, dwV = 0, dwelling = false;
  addLog('info', '시뮬레이션 모드');

  setInterval(() => {
    earV += (Math.random() - 0.5) * 0.024;
    if (Math.random() < 0.025) earV = 0.10 + Math.random() * 0.08;
    earV = Math.max(0.10, Math.min(0.48, earV));

    gx = Math.max(160, Math.min(1120, gx + (Math.random() - 0.5) * 16));
    gy = Math.max(80,  Math.min(720,  gy + (Math.random() - 0.5) * 11));

    if (Math.random() < 0.012) dwelling = !dwelling;
    dwV = dwelling ? Math.min(100, dwV + 2.2) : Math.max(0, dwV - 3.8);

    setState(prev => ({
      ...prev,
      ear: parseFloat(earV.toFixed(3)),
      gaze: {
        cx: Math.round(gx), cy: Math.round(gy),
        rx: Math.round((gx - 640) / 5.8),
        ry: Math.round((gy - 400) / 3.9),
      },
      dwell: parseFloat(dwV.toFixed(1)),
      fsm: dwV >= 100 ? 'MOVING' : earV < 0.20 ? 'GRIP' : 'IDLE',
    }));
  }, 80);
}
