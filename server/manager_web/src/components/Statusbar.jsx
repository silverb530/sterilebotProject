import { C } from "../styles";

function SbItem({ ok, label }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:5, fontSize:11, color:"rgba(255,255,255,.9)" }}>
      <div style={{ width:6, height:6, borderRadius:"50%", background: ok ? "#6BCB6B" : "rgba(255,255,255,.4)" }}/>
      {label}
    </div>
  );
}

export default function Statusbar({ msg }) {
  return (
    <div style={{
      height: 24, flexShrink: 0,
      background: C.accent,
      display: "flex", alignItems: "center",
      padding: "0 12px", gap: 14,
    }}>
      <SbItem ok label="myCobot (192.168.0.20)"/>
      <SbItem ok label="소켓 (9001)"/>
      <SbItem ok={false} label="OV9281 대기"/>
      <span style={{ marginLeft:"auto", fontSize:11, color:"rgba(255,255,255,.75)", fontFamily:C.mono }}>
        {msg}
      </span>
    </div>
  );
}
