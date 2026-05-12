import { useState, useEffect } from 'react';
import { useFlask } from './hooks/useFlask';
import TopBar from './components/TopBar';
import TabBar from './components/TabBar';
import LogStrip from './components/LogStrip';
import GazeTab from './tabs/GazeTab';
import GripperTab from './tabs/GripperTab';
import OverviewTab from './tabs/OverviewTab';

export default function App() {
  const [activeTab, setActiveTab] = useState('gaze');
  const { state, connected, logs, setLogs, addLog, triggerStop, toggleGaze, setGripper } = useFlask();

  // 스페이스바 긴급정지
  useEffect(() => {
    const handler = (e) => { if (e.code === 'Space') { e.preventDefault(); triggerStop(); } };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [triggerStop]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <TopBar fsm={state.fsm} connected={connected} />
      <TabBar active={activeTab} onChange={setActiveTab} />

      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        <div style={{
          position: 'absolute', inset: 0,
          display: activeTab === 'gaze' ? 'flex' : 'none',
          flexDirection: 'column', padding: '14px 16px', overflowY: 'auto', gap: 14,
        }}>
          <GazeTab state={state} triggerStop={triggerStop} />
        </div>

        <div style={{
          position: 'absolute', inset: 0,
          display: activeTab === 'gripper' ? 'flex' : 'none',
          flexDirection: 'column', padding: '14px 16px', overflowY: 'auto', gap: 14,
        }}>
          <GripperTab state={state} triggerStop={triggerStop} toggleGaze={toggleGaze} setGripper={setGripper} addLog={addLog} />
        </div>

        <div style={{
          position: 'absolute', inset: 0,
          display: activeTab === 'overview' ? 'flex' : 'none',
          flexDirection: 'column', padding: '14px 16px', overflowY: 'auto', gap: 14,
        }}>
          <OverviewTab />
        </div>
      </div>

      <LogStrip logs={logs} setLogs={setLogs} />
    </div>
  );
}
