import { useState } from "react";
import { C, Card, Btn, SettingToggle, SettingInput, s } from "../styles";

export default function Settings({ setStatus }) {
  const [g, setG] = useState({ autoConn:true, autoSave:true, restore:false });
  const [conn, setConn] = useState({ ip:"192.168.0.20", port:"9001", flask:"5000" });
  const [cam, setCam] = useState({ res:"640 × 480", fps:"60", overlay:true });
  const [alert, setAlert] = useState({ safety:true, disc:true, train:true });

  const save = () => {
    fetch("/api/settings", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ ...g, ...conn, ...cam, ...alert }),
    }).then(() => setStatus("설정 저장됨"));
  };

  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        <div style={s.col}>
          <Card title="일반 설정">
            <SettingToggle name="자동 연결" desc="앱 시작 시 myCobot 자동 연결" checked={g.autoConn} onChange={e=>setG(p=>({...p,autoConn:e.target.checked}))}/>
            <SettingToggle name="자동 저장" desc="캘리브레이션 데이터 변경 시 CSV 자동 저장" checked={g.autoSave} onChange={e=>setG(p=>({...p,autoSave:e.target.checked}))}/>
            <SettingToggle name="마지막 세션 복원" desc="이전 캘리브레이션 상태를 자동으로 불러옵니다" checked={g.restore} onChange={e=>setG(p=>({...p,restore:e.target.checked}))}/>
          </Card>
          <Card title="연결 설정">
            <SettingInput name="myCobot IP" desc="로봇 네트워크 주소" value={conn.ip} onChange={e=>setConn(p=>({...p,ip:e.target.value}))}/>
            <SettingInput name="소켓 포트" desc="C++ ↔ Python 통신 포트" value={conn.port} onChange={e=>setConn(p=>({...p,port:e.target.value}))}/>
            <SettingInput name="Flask 포트" desc="웹 모니터링 서버 포트" value={conn.flask} onChange={e=>setConn(p=>({...p,flask:e.target.value}))}/>
          </Card>
        </div>

        <div style={s.col}>
          <Card title="카메라 설정">
            <SettingInput name="해상도" desc="OV9281 캡처 해상도" value={cam.res} onChange={e=>setCam(p=>({...p,res:e.target.value}))}/>
            <SettingInput name="프레임율" desc="초당 캡처 프레임 수" value={cam.fps} onChange={e=>setCam(p=>({...p,fps:e.target.value}))}/>
            <SettingToggle name="동공 추적 오버레이" desc="카메라 뷰에 동공 위치 표시" checked={cam.overlay} onChange={e=>setCam(p=>({...p,overlay:e.target.checked}))}/>
          </Card>
          <Card title="알림 설정">
            <SettingToggle name="안전 경고 알림" desc="안전 반경 초과 시 팝업 알림" checked={alert.safety} onChange={e=>setAlert(p=>({...p,safety:e.target.checked}))}/>
            <SettingToggle name="연결 해제 알림" desc="로봇/카메라 연결 해제 시 경고" checked={alert.disc} onChange={e=>setAlert(p=>({...p,disc:e.target.checked}))}/>
            <SettingToggle name="학습 완료 알림" desc="CNN/YOLO 학습 완료 시 알림" checked={alert.train} onChange={e=>setAlert(p=>({...p,train:e.target.checked}))}/>
          </Card>
          <div style={{ display:"flex", gap:8 }}>
            <Btn primary style={{ flex:1 }} onClick={save}>설정 저장</Btn>
            <Btn style={{ flex:1 }}>기본값으로</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
