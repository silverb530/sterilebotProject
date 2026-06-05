import { C } from "../styles";
const ITEMS = [
  { key:"dashboard",   icon:"📊", label:"대시보드" },
  { key:"researchers", icon:"👥", label:"연구원 관리" },
  { key:"settings",    icon:"⚙️", label:"시스템 설정" },
];
export default function Sidebar({ tab, setTab }) {
  return (
    <div style={{ width:200, flexShrink:0, background:C.sidebar, display:"flex", flexDirection:"column", color:"#fff" }}>
      <div style={{ padding:"18px 16px 14px", borderBottom:"1px solid rgba(255,255,255,.08)", display:"flex", alignItems:"center", gap:10 }}>
        <div style={{ width:34, height:34, borderRadius:8, background:C.accent, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16, fontWeight:700 }}>C</div>
        <div><div style={{ fontSize:14, fontWeight:600 }}>ChemiBot</div><div style={{ fontSize:10, color:"rgba(255,255,255,.4)", marginTop:1 }}>전체관리자 · Admin</div></div>
      </div>
      <div style={{ padding:"12px 16px 4px", fontSize:10, color:"rgba(255,255,255,.35)", fontWeight:600, letterSpacing:.5 }}>관리 메뉴</div>
      <div style={{ display:"flex", flexDirection:"column", gap:2, padding:"4px 8px" }}>
        {ITEMS.map(i => (
          <button key={i.key} onClick={() => setTab(i.key)} style={{
            height:38, padding:"0 12px", display:"flex", alignItems:"center", gap:10,
            borderRadius:6, cursor:"pointer", fontSize:13, border:"none", textAlign:"left",
            fontFamily:"'Noto Sans KR',sans-serif", width:"100%", transition:"all .12s",
            background: tab===i.key ? C.accent : "transparent",
            color: tab===i.key ? "#fff" : "rgba(255,255,255,.6)",
            fontWeight: tab===i.key ? 500 : 400,
          }}>
            <span style={{ fontSize:15 }}>{i.icon}</span>{i.label}
          </button>
        ))}
      </div>
      <div style={{ flex:1 }}/>
      <div style={{ padding:"12px 16px 18px", borderTop:"1px solid rgba(255,255,255,.08)" }}>
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <div style={{ width:7, height:7, borderRadius:"50%", background:"#34C759" }}/>
          <span style={{ fontSize:11, color:"rgba(255,255,255,.5)" }}>시스템 정상 작동 중</span>
        </div>
      </div>
    </div>
  );
}
