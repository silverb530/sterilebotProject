const TABS = [
  { id: 'gaze',     icon: '👁', label: '동공·시선·센서' },
  { id: 'gripper',  icon: '🤖', label: '그리퍼·로봇·제어' },
  { id: 'overview', icon: '📷', label: '작업대 조감' },
];

export default function TabBar({ active, onChange }) {
  return (
    <div style={{
      flexShrink: 0, display: 'flex', alignItems: 'stretch',
      background: 'var(--surface)', borderBottom: '1px solid var(--border)',
      padding: '0 20px', gap: 2,
    }}>
      {TABS.map(t => (
        <div
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            padding: '9px 22px',
            fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: 1,
            color: active === t.id ? 'var(--teal)' : 'var(--text-dim)',
            cursor: 'pointer',
            borderBottom: active === t.id ? '2px solid var(--teal)' : '2px solid transparent',
            display: 'flex', alignItems: 'center', gap: 8,
            userSelect: 'none', transition: 'all .15s',
          }}
        >
          <span style={{ fontSize: 13 }}>{t.icon}</span>
          {t.label}
        </div>
      ))}
    </div>
  );
}
