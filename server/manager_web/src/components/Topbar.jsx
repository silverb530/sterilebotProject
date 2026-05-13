import { C, Btn } from "../styles";

function StatusDot({ color }) {
  const bg = { green:"#34C759", amber:"#FF9500", red:"#FF3B30" }[color];
  return <div style={{ width:7, height:7, borderRadius:"50%", background:bg, flexShrink:0 }}/>;
}
function SI({ dot, label }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", gap:5,
      padding:"4px 10px", borderRadius:20,
      background:"#F9F9F9", fontSize:11, fontWeight:500, height:28,
    }}>
      <StatusDot color={dot}/><span>{label}</span>
    </div>
  );
}

export default function Topbar({ title, sub, onStartCalib }) {
  return (
    <div style={{
      height: 48, flexShrink: 0,
      background: C.surface,
      borderBottom: `1px solid ${C.border}`,
      display: "flex", alignItems: "center",
      padding: "0 10px 0 18px", gap: 6,
    }}>
      <span style={{ fontSize:16, fontWeight:600 }}>{title}</span>
      <span style={{ fontSize:12, color:C.textDim, marginLeft:4 }}>{sub}</span>

      <div style={{ width:1, height:22, background:C.border, margin:"0 6px" }}/>

      <div style={{ display:"flex", alignItems:"center", gap:8, marginLeft:4 }}>
        <SI dot="green" label="연결됨"/>
        <SI dot="green" label="안전 상태"/>
        <SI dot="amber" label="AI 모델 활성화"/>
      </div>

      <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:6 }}>
        <Btn onClick={()=>alert("ONNX 내보내기")}>ONNX 내보내기</Btn>
        <Btn primary onClick={onStartCalib}>▶ &nbsp;캘리브레이션 시작</Btn>
      </div>
    </div>
  );
}
