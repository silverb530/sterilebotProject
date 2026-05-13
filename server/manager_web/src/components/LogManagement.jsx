import { useState, useEffect } from "react";
import { C, Card, Btn } from "../styles";

const LEVEL_COLOR = { OK:C.green, WARN:C.amber, ERROR:C.red, INFO:C.accent };

export default function LogManagement({ setStatus }) {
  const [logs, setLogs] = useState([]);

  const refresh = () => {
    fetch("/api/logs").then(r => r.json()).then(setLogs);
  };

  useEffect(() => { refresh(); }, []);

  const clear = () => {
    if (!confirm("모든 로그를 삭제하시겠습니까?")) return;
    fetch("/api/logs/clear", { method:"POST" }).then(() => { setLogs([]); setStatus("로그 삭제됨"); });
  };

  return (
    <div style={{ height:"100%", padding:14, display:"flex", flexDirection:"column" }}>
      <Card
        title="시스템 로그"
        action={
          <div style={{ display:"flex", gap:6 }}>
            <Btn small danger onClick={clear}>로그 삭제</Btn>
            <Btn small onClick={refresh}>새로고침</Btn>
          </div>
        }
        style={{ flex:1, display:"flex", flexDirection:"column" }}
      >
        <div style={{ overflowY:"auto", margin:"-12px -14px -12px" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr>
                {["시간","레벨","모듈","메시지"].map(h => (
                  <th key={h} style={{
                    textAlign:"left", padding:"6px 10px",
                    borderBottom:`2px solid ${C.border}`,
                    color:C.textDim, fontSize:11, fontWeight:600,
                    position:"sticky", top:0, background:C.surface,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((l, i) => (
                <tr key={i} style={{ background: i%2===1 ? C.surface2 : C.surface }}>
                  <td style={{ padding:"5px 10px", fontFamily:C.mono, fontSize:11, color:C.textDim }}>{l.time}</td>
                  <td style={{ padding:"5px 10px", fontWeight:600, color: LEVEL_COLOR[l.level]||C.text }}>{l.level}</td>
                  <td style={{ padding:"5px 10px", color:C.textMid }}>{l.module}</td>
                  <td style={{ padding:"5px 10px" }}>{l.msg}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 && (
            <div style={{ textAlign:"center", padding:32, color:C.textDim, fontSize:13 }}>로그가 없습니다.</div>
          )}
        </div>
      </Card>
    </div>
  );
}
