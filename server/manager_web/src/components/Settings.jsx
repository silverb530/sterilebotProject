import { useState, useEffect } from "react";
import { C } from "../styles";

function SettingRow({ name, desc, value, onChange }) {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 0", borderBottom:`1px solid ${C.border}` }}>
      <div><div style={{ fontSize:13, fontWeight:500 }}>{name}</div><div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{desc}</div></div>
      <input value={value} onChange={onChange} style={{ height:28, width:130, padding:"0 8px", border:`1px solid ${C.border2}`, borderRadius:6, fontFamily:"Consolas", fontSize:12, background:C.surface }}/>
    </div>
  );
}

export default function Settings() {
  const [s, setS] = useState(null);
  useEffect(() => { fetch("/api/settings").then(r => r.json()).then(setS); }, []);
  if (!s) return <div style={{ padding:20, color:C.textDim }}>로딩 중...</div>;
  const set = (k) => (e) => setS(p => ({ ...p, [k]:e.target.value }));
  const save = () => fetch("/api/settings", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(s) }).then(() => alert("설정이 저장되었습니다."));
  const Card = ({ icon, title, children }) => (
    <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
      <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600 }}>{icon} {title}</div>
      <div style={{ padding:"14px 16px" }}>{children}</div>
    </div>
  );
  return (
    <div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Card icon="🔌" title="장비 연결 설정">
          <SettingRow name="myCobot IP" desc="로봇 네트워크 주소" value={s.robot_ip} onChange={set("robot_ip")}/>
          <SettingRow name="소켓 포트" desc="C++ ↔ Python 통신 포트" value={s.socket_port} onChange={set("socket_port")}/>
          <SettingRow name="Flask 포트" desc="웹 모니터링 서버 포트" value={s.flask_port} onChange={set("flask_port")}/>
        </Card>
        <Card icon="💨" title="가스 농도 경고 기준">
          <SettingRow name="경고 기준 (ppm)" desc="이 값 초과 시 주의 알림" value={s.gas_warn} onChange={set("gas_warn")}/>
          <SettingRow name="위험 기준 (ppm)" desc="이 값 초과 시 비상 알림" value={s.gas_danger} onChange={set("gas_danger")}/>
        </Card>
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginTop:14 }}>
        <Card icon="🌡️" title="온도 경고 기준">
          <SettingRow name="최저 온도 (°C)" desc="이 값 미만 시 경고" value={s.temp_min} onChange={set("temp_min")}/>
          <SettingRow name="최고 온도 (°C)" desc="이 값 초과 시 경고" value={s.temp_max} onChange={set("temp_max")}/>
        </Card>
        <Card icon="💧" title="습도 경고 기준">
          <SettingRow name="최저 습도 (%)" desc="이 값 미만 시 경고" value={s.humid_min} onChange={set("humid_min")}/>
          <SettingRow name="최고 습도 (%)" desc="이 값 초과 시 경고" value={s.humid_max} onChange={set("humid_max")}/>
        </Card>
      </div>
      <div style={{ display:"flex", gap:8, justifyContent:"flex-end", marginTop:10 }}>
        <button onClick={save} style={{ height:32, padding:"0 14px", background:C.accent, border:`1px solid ${C.accent}`, borderRadius:6, fontSize:12, color:"#fff", fontWeight:500, cursor:"pointer" }}>💾 설정 저장</button>
      </div>
    </div>
  );
}
