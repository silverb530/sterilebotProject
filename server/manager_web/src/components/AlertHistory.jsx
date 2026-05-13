import { useState, useEffect } from "react";
import { C, Card, Badge } from "../styles";

const TYPE_BADGE = { error:"err", warn:"warn", ok:"ok", info:"info" };

export default function AlertHistory() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    fetch("/api/alerts").then(r => r.json()).then(setAlerts);
  }, []);

  return (
    <div style={{ height:"100%", padding:14, display:"flex", flexDirection:"column" }}>
      <Card
        title="알림 이력"
        badge={<Badge type="warn">{alerts.length}건</Badge>}
        style={{ flex:1 }}
      >
        {alerts.map((a, i) => (
          <div key={i} style={{
            display:"flex", gap:12, padding:"10px 0",
            borderBottom: i < alerts.length-1 ? `1px solid ${C.border}` : "none",
          }}>
            <div style={{
              width:30, height:30, borderRadius:6,
              background:C.surface2, border:`1px solid ${C.border}`,
              display:"flex", alignItems:"center", justifyContent:"center",
              flexShrink:0, fontSize:13,
            }}>{a.icon}</div>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:13, fontWeight:500 }}>{a.title}</div>
              <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{a.desc}</div>
              <div style={{ fontFamily:C.mono, fontSize:10, color:C.textDim, marginTop:3 }}>{a.time}</div>
            </div>
            <Badge type={TYPE_BADGE[a.type]||"info"}>{a.type}</Badge>
          </div>
        ))}
        {alerts.length === 0 && (
          <div style={{ textAlign:"center", padding:32, color:C.textDim, fontSize:13 }}>알림이 없습니다.</div>
        )}
      </Card>
    </div>
  );
}
