// 공용 인라인 스타일 헬퍼
export const C = {
  accent:     "#3B46CF",
  accentH:    "#2D38B0",
  accentDim:  "#3B46CF18",
  bg:         "#F3F3F3",
  surface:    "#FFFFFF",
  surface2:   "#F9F9F9",
  border:     "#E0E0E0",
  border2:    "#C8C8C8",
  text:       "#1A1A1A",
  textMid:    "#444444",
  textDim:    "#888888",
  green:      "#0F7B0F",
  greenDim:   "#0F7B0F15",
  amber:      "#9D5D00",
  amberDim:   "#9D5D0015",
  red:        "#C42B1C",
  redDim:     "#C42B1C15",
  sidebar:    "#1B1F3B",
  mono:       "'Consolas','Courier New',monospace",
  sans:       "'Noto Sans KR','Segoe UI',sans-serif",
  r:          "6px",
};

export const s = {
  card: {
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: C.r,
    boxShadow: "0 1px 4px rgba(0,0,0,.06)",
  },
  cardHeader: {
    padding: "10px 14px",
    borderBottom: `1px solid ${C.border}`,
    fontSize: 13,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cardBody: {
    padding: "12px 14px",
  },
  label: {
    fontSize: 11,
    color: C.textDim,
    fontWeight: 500,
    marginBottom: 4,
  },
  row2: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 12,
    alignItems: "start",
  },
  col: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
};

// 버튼 컴포넌트
export function Btn({ children, primary, danger, small, onClick, style = {} }) {
  return (
    <button
      onClick={onClick}
      style={{
        height: small ? 26 : 30,
        padding: small ? "0 10px" : "0 14px",
        background: primary ? C.accent : danger ? C.redDim : C.surface,
        border: `1px solid ${primary ? C.accent : danger ? C.red : C.border2}`,
        borderRadius: C.r,
        fontFamily: C.sans,
        fontSize: small ? 11 : 12,
        color: primary ? "#fff" : danger ? C.red : C.textMid,
        fontWeight: primary ? 500 : 400,
        cursor: "pointer",
        transition: "all .12s",
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// 뱃지
export function Badge({ children, type = "info" }) {
  const colors = {
    ok:   { bg: C.greenDim,  color: C.green },
    warn: { bg: C.amberDim,  color: C.amber },
    err:  { bg: C.redDim,    color: C.red },
    info: { bg: C.accentDim, color: C.accent },
  };
  const c = colors[type] || colors.info;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "2px 9px", borderRadius: 20,
      background: c.bg, color: c.color,
      fontSize: 11, fontWeight: 500,
    }}>
      {children}
    </span>
  );
}

// 카드 컴포넌트
export function Card({ title, badge, action, children, style = {} }) {
  return (
    <div style={{ ...s.card, ...style }}>
      <div style={s.cardHeader}>
        <span style={{ display:"flex", alignItems:"center", gap:8 }}>
          {title}
          {badge}
        </span>
        {action}
      </div>
      <div style={s.cardBody}>{children}</div>
    </div>
  );
}

// 카메라 박스
export function CamBox({ label, sub, fps, height = 140, icon = "📷", msg = "스트림 대기 중..." }) {
  return (
    <div style={{
      background: "#0D0D0D", borderRadius: C.r,
      height, position: "relative", overflow: "hidden",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{ position:"absolute", top:7, left:9, display:"flex", gap:10 }}>
        {label && <span style={{ fontFamily:C.mono, fontSize:10, color:"rgba(255,255,255,.45)" }}>{label}</span>}
        {sub && <span style={{ fontFamily:C.mono, fontSize:10, color:"rgba(255,255,255,.45)" }}>{sub}</span>}
      </div>
      {fps && <div style={{ position:"absolute", top:7, right:9, fontFamily:C.mono, fontSize:10, color:"#34C759" }}>{fps}</div>}
      <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:6, color:"#555" }}>
        <span style={{ fontSize:28, opacity:.4 }}>{icon}</span>
        <span style={{ fontSize:11 }}>{msg}</span>
      </div>
    </div>
  );
}

// 토글 스위치
export function Toggle({ checked, onChange }) {
  return (
    <label style={{ position:"relative", width:36, height:20, flexShrink:0, cursor:"pointer" }}>
      <input type="checkbox" checked={checked} onChange={onChange}
        style={{ opacity:0, width:0, height:0, position:"absolute" }} />
      <span style={{
        position:"absolute", inset:0,
        background: checked ? C.accent : C.border2,
        borderRadius: 10, transition: ".2s",
      }}>
        <span style={{
          position:"absolute",
          width:14, height:14,
          left: checked ? 19 : 3, bottom:3,
          background:"#fff", borderRadius:"50%",
          transition: ".2s",
          boxShadow:"0 1px 3px rgba(0,0,0,.2)",
        }}/>
      </span>
    </label>
  );
}

// 진행바
export function ProgressBar({ value, max = 16 }) {
  const pct = Math.round(value / max * 100);
  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5, fontSize:12, color:C.textDim }}>
        <span>진행도</span><span style={{ fontFamily:C.mono, fontWeight:600 }}>{value} / {max}</span>
      </div>
      <div style={{ height:5, background:C.border, borderRadius:3, overflow:"hidden" }}>
        <div style={{ height:"100%", width:`${pct}%`, background:C.accent, borderRadius:3, transition:"width .3s" }}/>
      </div>
    </div>
  );
}

// 파라미터 행
export function ParamRow({ name, desc, value, onChange, unit }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"10px 0", borderBottom:`1px solid ${C.border}`,
    }}>
      <div>
        <div style={{ fontSize:13, fontWeight:500 }}>{name}</div>
        <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{desc}</div>
      </div>
      <div style={{ display:"flex", alignItems:"center", gap:6 }}>
        <input value={value} onChange={onChange} style={{
          height:30, width:90, padding:"0 8px", textAlign:"center",
          border:`1px solid ${C.border2}`, borderRadius:C.r,
          fontFamily:C.mono, fontSize:13, fontWeight:600, background:C.surface,
        }}/>
        {unit && <span style={{ fontSize:11, color:C.textDim, minWidth:20 }}>{unit}</span>}
      </div>
    </div>
  );
}

// 설정 행 (토글)
export function SettingToggle({ name, desc, checked, onChange }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"10px 0", borderBottom:`1px solid ${C.border}`,
    }}>
      <div>
        <div style={{ fontSize:13, fontWeight:500 }}>{name}</div>
        <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{desc}</div>
      </div>
      <Toggle checked={checked} onChange={onChange}/>
    </div>
  );
}

// 설정 행 (입력)
export function SettingInput({ name, desc, value, onChange }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"10px 0", borderBottom:`1px solid ${C.border}`,
    }}>
      <div>
        <div style={{ fontSize:13, fontWeight:500 }}>{name}</div>
        <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{desc}</div>
      </div>
      <input value={value} onChange={onChange} style={{
        height:28, width:130, padding:"0 8px",
        border:`1px solid ${C.border2}`, borderRadius:C.r,
        fontFamily:C.mono, fontSize:12, background:C.surface,
      }}/>
    </div>
  );
}

// 연결 행
export function ConnRow({ name, badge }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"8px 0", borderBottom:`1px solid ${C.border}`,
    }}>
      <span style={{ fontSize:13, color:C.textMid }}>{name}</span>
      {badge}
    </div>
  );
}
