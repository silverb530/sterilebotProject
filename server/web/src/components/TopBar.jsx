import { useState, useEffect } from 'react';

const FSM_MAP = {
  IDLE:  { cls: 'idle',   lbl: 'IDLE' },
  MOVING:{ cls: 'moving', lbl: 'MOVING' },
  GRIP:  { cls: 'grip',   lbl: 'GRIP' },
  ESTOP: { cls: 'stop',   lbl: 'E-STOP' },
};

export default function TopBar({ fsm, connected }) {
  const [clock, setClock] = useState('--:--:--');
  const m = FSM_MAP[fsm] ?? FSM_MAP.IDLE;

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toTimeString().slice(0, 8)), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{
      flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '9px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)',
    }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 500, letterSpacing: 3, color: 'var(--teal)' }}>
        STERILE<span style={{ color: 'var(--text-dim)' }}>BOT</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: connected ? 'var(--teal)' : 'var(--red)',
          animation: 'pulse 2s infinite',
        }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: connected ? 'var(--teal)' : 'var(--red)' }}>
          {connected ? 'FLASK 연결됨' : 'FLASK 연결 안됨'}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 7,
          padding: '4px 13px', borderRadius: 4,
          fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, letterSpacing: 1,
          border: '1px solid',
          ...(m.cls === 'idle'   ? { background: 'var(--teal-dim)',  borderColor: 'var(--teal)',  color: 'var(--teal)' }  : {}),
          ...(m.cls === 'moving' ? { background: 'var(--blue-dim)',  borderColor: 'var(--blue)',  color: 'var(--blue)' }  : {}),
          ...(m.cls === 'grip'   ? { background: 'var(--amber-dim)', borderColor: 'var(--amber)', color: 'var(--amber)' } : {}),
          ...(m.cls === 'stop'   ? { background: 'var(--red-dim)',   borderColor: 'var(--red)',   color: 'var(--red)' }   : {}),
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', animation: 'pulse 1.3s infinite' }} />
          {m.lbl}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text-mid)' }}>{clock}</div>
      </div>
    </div>
  );
}
