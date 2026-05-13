import { C, Btn } from "../styles";

const STEPS = [
  { n:1, title:"마커 배치",         desc:"작업대에 4×4 마커 16개를 배치합니다." },
  { n:2, title:"로봇 좌표 측정",    desc:"수동 제어에서 로봇팔로 각 마커의 XYZ 좌표를 측정합니다." },
  { n:3, title:"시선 캘리브레이션", desc:"아이트래커 착용 후 마커를 순서대로 3초씩 응시합니다." },
  { n:4, title:"모델 학습 & 내보내기", desc:"모델 관리에서 CNN 학습 후 ONNX를 내보냅니다." },
  { n:5, title:"팀 정보",           desc:"김규대(팀장) · 김수영(총무) · 정서현 · 강은비\n한남대학교 관광호텔경영학과" },
];

export default function HelpModal({ onClose }) {
  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"rgba(0,0,0,.4)",
      display:"flex", alignItems:"center", justifyContent:"center", zIndex:999,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background:C.surface, borderRadius:8,
        boxShadow:"0 12px 40px rgba(0,0,0,.25)",
        width:560, maxHeight:"80vh", overflow:"hidden",
        display:"flex", flexDirection:"column",
      }}>
        <div style={{
          padding:"14px 18px", borderBottom:`1px solid ${C.border}`,
          display:"flex", alignItems:"center", justifyContent:"space-between",
        }}>
          <h3 style={{ fontSize:15, fontWeight:600 }}>SterileBot — 도움말</h3>
          <button onClick={onClose} style={{
            width:26, height:26, border:"none", background:"transparent",
            borderRadius:4, cursor:"pointer", fontSize:16, color:C.textDim,
          }}>✕</button>
        </div>
        <div style={{ padding:18, overflowY:"auto" }}>
          {STEPS.map(({ n, title, desc }) => (
            <div key={n} style={{
              display:"flex", gap:12, alignItems:"flex-start",
              padding:"10px 0", borderBottom:`1px solid ${C.border}`,
            }}>
              <div style={{
                width:26, height:26, borderRadius:"50%",
                background:C.accent, color:"#fff",
                fontFamily:C.mono, fontSize:12, fontWeight:700,
                display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0,
              }}>{n}</div>
              <div>
                <div style={{ fontSize:13, fontWeight:600, marginBottom:3 }}>{title}</div>
                <div style={{ fontSize:12, color:C.textMid, lineHeight:1.6, whiteSpace:"pre-line" }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
