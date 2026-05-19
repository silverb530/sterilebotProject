import { useState, useEffect } from "react";
import { C } from "../styles";

function Badge({ type, children }) {
  const colors = { ok:{bg:C.greenDim,c:C.green}, warn:{bg:C.amberDim,c:C.amber}, err:{bg:C.redDim,c:C.red}, info:{bg:C.accentDim,c:C.accent} };
  const cl = colors[type] || colors.info;
  return <span style={{ display:"inline-flex", padding:"2px 10px", borderRadius:20, fontSize:11, fontWeight:500, background:cl.bg, color:cl.c }}>{children}</span>;
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  useEffect(() => { fetch("/api/dashboard").then(r => r.json()).then(setData); }, []);
  if (!data) return <div style={{ padding:20, color:C.textDim }}>로딩 중...</div>;
  return (
    <div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:16 }}>
        {[
          { n:data.total_researchers, l:"등록 연구원", c:C.accent },
          { n:data.face_registered,   l:"얼굴 등록 완료", c:C.green },
          { n:data.total_usage,       l:"총 실험 횟수", c:C.accent },
          { n:data.total_errors,      l:"오류/비상정지", c:C.red },
        ].map((s,i) => (
          <div key={i} style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, padding:16, textAlign:"center", boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
            <div style={{ fontSize:28, fontWeight:700, fontFamily:"Consolas,monospace", color:s.c }}>{s.n}</div>
            <div style={{ fontSize:11, color:C.textDim, marginTop:4 }}>{s.l}</div>
          </div>
        ))}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
          <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600 }}>최근 실험 기록</div>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead><tr>{["날짜","연구원","시작","종료","상태"].map(h=><th key={h} style={{ textAlign:"left", padding:"8px 12px", borderBottom:`2px solid ${C.border}`, color:C.textDim, fontSize:11, fontWeight:600 }}>{h}</th>)}</tr></thead>
            <tbody>{data.recent_usage.map((u,i) => (
              <tr key={i} style={{ background:i%2?C.surface2:C.surface }}><td style={{ padding:"7px 12px" }}>{u.date}</td><td style={{ padding:"7px 12px" }}>{u.researcher}</td><td style={{ padding:"7px 12px", fontFamily:"Consolas" }}>{u.start}</td><td style={{ padding:"7px 12px", fontFamily:"Consolas" }}>{u.end}</td><td style={{ padding:"7px 12px" }}><Badge type={u.status==="완료"?"ok":"err"}>{u.status}</Badge></td></tr>
            ))}</tbody>
          </table>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
          <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600 }}>최근 오류 이력</div>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead><tr>{["날짜","연구원","유형","설명"].map(h=><th key={h} style={{ textAlign:"left", padding:"8px 12px", borderBottom:`2px solid ${C.border}`, color:C.textDim, fontSize:11, fontWeight:600 }}>{h}</th>)}</tr></thead>
            <tbody>{data.recent_errors.map((e,i) => (
              <tr key={i} style={{ background:i%2?C.surface2:C.surface }}><td style={{ padding:"7px 12px" }}>{e.date}</td><td style={{ padding:"7px 12px" }}>{e.researcher}</td><td style={{ padding:"7px 12px" }}><Badge type={e.type==="비상정지"?"err":"warn"}>{e.type}</Badge></td><td style={{ padding:"7px 12px", fontSize:11 }}>{e.desc}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
