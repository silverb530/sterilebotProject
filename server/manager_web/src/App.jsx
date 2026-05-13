import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import Statusbar from "./components/Statusbar";
import Dashboard from "./components/Dashboard";
import Calibration from "./components/Calibration";
import ManualControl from "./components/ManualControl";
import Parameters from "./components/Parameters";
import ModelManagement from "./components/ModelManagement";
import LogManagement from "./components/LogManagement";
import AlertHistory from "./components/AlertHistory";
import Settings from "./components/Settings";
import HelpModal from "./components/HelpModal";

const TAB_META = {
  dashboard: { title: "대시보드",    sub: "시선 추적 · 안전 설정" },
  calib:     { title: "캘리브레이션", sub: "마커 그리드 · 동공 매핑" },
  manual:    { title: "수동 제어",   sub: "좌표 직접 입력 · 슬라이더" },
  params:    { title: "파라미터",    sub: "시선 · 로봇 파라미터" },
  models:    { title: "모델 관리",   sub: "Gaze CNN · YOLOv8" },
  logs:      { title: "로그 관리",   sub: "시스템 로그 뷰어" },
  alerts:    { title: "알림 이력",   sub: "경고 · 정보 알림" },
  settings:  { title: "설정",       sub: "연결 · 카메라 · 알림" },
};

export default function App() {
  const [tab, setTab]           = useState("dashboard");
  const [statusMsg, setStatusMsg] = useState("준비");
  const [helpOpen, setHelpOpen] = useState(false);

  const setStatus = useCallback((msg) => setStatusMsg(msg), []);
  const meta = TAB_META[tab];

  const panes = {
    dashboard: <Dashboard setStatus={setStatus} />,
    calib:     <Calibration setStatus={setStatus} />,
    manual:    <ManualControl setStatus={setStatus} />,
    params:    <Parameters setStatus={setStatus} />,
    models:    <ModelManagement setStatus={setStatus} />,
    logs:      <LogManagement setStatus={setStatus} />,
    alerts:    <AlertHistory />,
    settings:  <Settings setStatus={setStatus} />,
  };

  return (
    <div style={{ display:"flex", width:"100vw", height:"100vh", background:"var(--bg)", overflow:"hidden" }}>
      <Sidebar activeTab={tab} onTabChange={setTab} onHelp={() => setHelpOpen(true)} />
      <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
        <Topbar title={meta.title} sub={meta.sub} onStartCalib={() => setTab("calib")} />
        <div style={{ flex:1, overflow:"hidden", position:"relative" }}>
          {panes[tab]}
        </div>
        <Statusbar msg={statusMsg} />
      </div>
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
    </div>
  );
}
