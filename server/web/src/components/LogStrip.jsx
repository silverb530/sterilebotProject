import { useState, useEffect, useRef } from 'react';

export default function LogStrip({ logs, setLogs }) {
  const [filter, setFilter] = useState('all');
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [logs]);

  const filtered = filter === 'all' ? logs : logs.filter(l => l.type === filter);

  const TAG_STYLE = {
    info: { background: 'var(--blue-dim)',  color: 'var(--blue)' },
    ok:   { background: 'var(--teal-dim)',  color: 'var(--teal)' },
    warn: { background: 'var(--amber-dim)', color: 'var(--amber)' },
    err:  { background: 'var(--red-dim)',   color: 'var(--red)' },
  };

  const FILTERS = ['all', 'ok', 'info', 'warn', 'err'];

  return (
    <div style={{
      flexShrink: 0, background: 'var(--surface)', borderTop: '1px solid var(--border)',
      height: 'var(--log-h)', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 14px', borderBottom: '1px solid var(--border)', flexShrink: 0,
      }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: 2, color: 'var(--text-dim)' }}>
          시스템 로그
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {FILTERS.map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '2px 9px', borderRadius: 3,
                border: `1px solid ${filter === f ? 'var(--teal)' : 'var(--border)'}`,
                background: filter === f ? 'var(--teal-dim)' : 'transparent',
                fontFamily: 'var(--mono)', fontSize: 10,
                color: filter === f ? 'var(--teal)' : 'var(--text-dim)',
                cursor: 'pointer',
              }}>
                {f.toUpperCase()}
              </button>
            ))}
          </div>
          <button onClick={() => setLogs([])} style={{
            fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)',
            background: 'none', border: 'none', cursor: 'pointer', padding: '2px 8px',
          }}>
            지우기
          </button>
        </div>
      </div>

      <div ref={bodyRef} style={{
        flex: 1, overflowY: 'auto', padding: '4px 14px',
        display: 'flex', flexDirection: 'column', gap: 1,
      }}>
        {filtered.map((l, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'baseline', gap: 10,
            padding: '2px 0', borderBottom: '1px solid #ffffff04',
          }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)', flexShrink: 0, width: 60 }}>
              {l.ts}
            </span>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 10, width: 38, textAlign: 'center',
              borderRadius: 3, padding: '0 4px', flexShrink: 0,
              ...(TAG_STYLE[l.type] ?? TAG_STYLE.info),
            }}>
              {l.type.toUpperCase()}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-mid)' }}>
              {l.msg}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
