import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import Dashboard from "./components/Dashboard";
import Researchers from "./components/Researchers";
import Settings from "./components/Settings";

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const pages = {
    dashboard: <Dashboard />,
    researchers: <Researchers />,
    settings: <Settings />,
  };
  return (
    <div style={{ display:"flex", width:"100vw", height:"100vh", overflow:"hidden", fontFamily:"'Noto Sans KR','Segoe UI',sans-serif", fontSize:13, color:"#1A1A1A", background:"#F3F3F3" }}>
      <Sidebar tab={tab} setTab={setTab} />
      <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
        <Topbar tab={tab} />
        <div style={{ flex:1, overflowY:"auto", padding:16 }}>
          {pages[tab]}
        </div>
      </div>
    </div>
  );
}
