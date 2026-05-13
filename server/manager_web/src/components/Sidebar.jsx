import { C } from "../styles";

const NAV_WORKSPACE = [
  { key:"dashboard", label:"대시보드",    icon:<rect x="1" y="1" width="6" height="6" rx="1"/>, icon2:<><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></> },
  { key:"calib",     label:"캘리브레이션", icon:null },
  { key:"manual",    label:"수동 제어",   icon:null },
  { key:"params",    label:"파라미터",    icon:null },
];
const NAV_MANAGE = [
  { key:"models",   label:"모델 관리" },
  { key:"logs",     label:"로그 관리" },
  { key:"alerts",   label:"알림 이력" },
  { key:"settings", label:"설정" },
];

const ICONS = {
  dashboard: <><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></>,
  calib:     <path d="M2 2v12h12V2H2zm1 1h10v10H3V3zm2 2v2h2V5H5zm4 0v2h2V5H9zM5 9v2h2V9H5zm4 0v2h2V9H9z"/>,
  manual:    <><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.5"/><circle cx="8" cy="8" r="2"/></>,
  params:    <path d="M3 4h10v1H3zm0 3h10v1H3zm0 3h7v1H3z"/>,
  models:    <path d="M8 1l7 4v6l-7 4L1 11V5l7-4zm0 1.5L2.5 6v4l5.5 3 5.5-3V6L8 2.5z"/>,
  logs:      <path d="M2 2h12v12H2V2zm1 1v10h10V3H3zm1 1h8v1H4V4zm0 2h8v1H4V6zm0 2h8v1H4V8zm0 2h5v1H4v-1z"/>,
  alerts:    <path d="M8 1a1 1 0 011 1v.3A5 5 0 0113 7v3l1 2H2l1-2V7A5 5 0 017 2.3V2a1 1 0 011-1zM6.5 13a1.5 1.5 0 003 0h-3z"/>,
  settings:  <path d="M8 5.5A2.5 2.5 0 108 10.5 2.5 2.5 0 008 5.5zM6 8a2 2 0 114 0 2 2 0 01-4 0z"/>,
  help:      <path d="M8 1a7 7 0 100 14A7 7 0 008 1zM2 8a6 6 0 1112 0A6 6 0 012 8zm5.2-2.5a.8.8 0 01.8-.8h.1a.8.8 0 01.7 1.1L8 8.5V10h1V8l.9-2.3A1.8 1.8 0 008.1 3.7H8a1.8 1.8 0 00-1.8 1.8H7.2zM8 11a1 1 0 100 2 1 1 0 000-2z"/>,
};

function NavItem({ icon, label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      height: 36, padding: "0 10px",
      display: "flex", alignItems: "center", gap: 9,
      borderRadius: 6, cursor: "pointer",
      fontSize: 13, color: active ? "#fff" : "rgba(255,255,255,.6)",
      border: "none", background: active ? C.accent : "transparent",
      textAlign: "left", fontFamily: C.sans, width: "100%",
      fontWeight: active ? 500 : 400, transition: "all .12s",
    }}>
      <svg viewBox="0 0 16 16" fill="currentColor" style={{ width:15, height:15, flexShrink:0, opacity: active?1:.7 }}>
        {icon}
      </svg>
      {label}
    </button>
  );
}

export default function Sidebar({ activeTab, onTabChange, onHelp }) {
  return (
    <div style={{
      width: 190, flexShrink: 0,
      background: C.sidebar,
      display: "flex", flexDirection: "column", color: "#fff",
    }}>
      {/* 브랜드 */}
      <div style={{
        padding: "16px 14px 12px",
        borderBottom: "1px solid rgba(255,255,255,.08)",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <div style={{
          width:32, height:32, borderRadius:8,
          background: C.accent,
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:15, fontWeight:700,
        }}>S</div>
        <div>
          <div style={{ fontSize:14, fontWeight:600 }}>SterileBot</div>
          <div style={{ fontSize:10, color:"rgba(255,255,255,.4)", marginTop:1 }}>Calibration · v2.0</div>
        </div>
      </div>

      {/* WORKSPACE */}
      <div style={{ padding:"10px 14px 4px", fontSize:10, color:"rgba(255,255,255,.35)", fontWeight:600, letterSpacing:.5 }}>WORKSPACE</div>
      <div style={{ display:"flex", flexDirection:"column", gap:2, padding:"4px 8px" }}>
        {[...NAV_WORKSPACE].map(({ key, label }) => (
          <NavItem key={key} icon={ICONS[key]} label={label}
            active={activeTab===key} onClick={()=>onTabChange(key)}/>
        ))}
      </div>

      {/* 관리 */}
      <div style={{ padding:"10px 14px 4px", fontSize:10, color:"rgba(255,255,255,.35)", fontWeight:600, letterSpacing:.5 }}>관리</div>
      <div style={{ display:"flex", flexDirection:"column", gap:2, padding:"4px 8px" }}>
        {NAV_MANAGE.map(({ key, label }) => (
          <NavItem key={key} icon={ICONS[key]} label={label}
            active={activeTab===key} onClick={()=>onTabChange(key)}/>
        ))}
      </div>

      <div style={{ flex:1 }}/>

      {/* 하단 */}
      <div style={{ padding:"8px 8px 0", borderTop:"1px solid rgba(255,255,255,.08)" }}>
        <NavItem icon={ICONS.help} label="도움말" active={false} onClick={onHelp}/>
      </div>
      <div style={{ padding:"10px 14px 16px", display:"flex", alignItems:"center", gap:8 }}>
        <div style={{ width:7, height:7, borderRadius:"50%", background:"#34C759", flexShrink:0 }}/>
        <div style={{ fontSize:11, color:"rgba(255,255,255,.5)" }}>myCobot · 192.168.0.20</div>
      </div>
    </div>
  );
}
