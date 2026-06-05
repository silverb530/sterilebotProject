import { useState, useEffect } from "react";
import { C } from "../styles";

function Badge({ type, children }) {
  const colors = { ok:{bg:C.greenDim,c:C.green}, warn:{bg:C.amberDim,c:C.amber}, err:{bg:C.redDim,c:C.red}, info:{bg:C.accentDim,c:C.accent} };
  const cl = colors[type] || colors.info;
  return <span style={{ display:"inline-flex", padding:"2px 10px", borderRadius:20, fontSize:11, fontWeight:500, background:cl.bg, color:cl.c }}>{children}</span>;
}

export default function Usage() {
  const [usage, setUsage] = useState([]);

  useEffect(() => {
    fetch("/api/usage").then(r => r.json()).then(setUsage);
  }, []);

  return (
    <div>
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
        <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600 }}>
          로봇 사용 기록
        </div>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead><tr>{["날짜","연구원","시작","종료","소요","상태"].map(h=><th key={h} style={{ textAlign:"left", padding:"8px 12px", borderBottom:`2px solid ${C.border}`, color:C.textDim, fontSize:11, fontWeight:600 }}>{h}</th>)}</tr></thead>
          <tbody>{usage.map((u,i) => {
            const [sh,sm]=u.start.split(":").map(Number), [eh,em]=u.end.split(":").map(Number);
            const dur=(eh*60+em)-(sh*60+sm);
            return (
              <tr key={i} style={{ background:i%2?C.surface2:C.surface }}>
                <td style={{ padding:"7px 12px" }}>{u.date}</td><td style={{ padding:"7px 12px", fontWeight:500 }}>{u.researcher}</td>
                <td style={{ padding:"7px 12px", fontFamily:"Consolas" }}>{u.start}</td><td style={{ padding:"7px 12px", fontFamily:"Consolas" }}>{u.end}</td>
                <td style={{ padding:"7px 12px", fontFamily:"Consolas" }}>{dur}분</td>
                <td style={{ padding:"7px 12px" }}><Badge type={u.status==="완료"?"ok":"err"}>{u.status}</Badge></td>
              </tr>);
          })}</tbody>
        </table>
      </div>
    </div>
  );
}
