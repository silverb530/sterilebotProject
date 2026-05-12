import { useEffect, useRef } from 'react';

export default function GripperTab({ state, triggerStop, toggleGaze, setGripper, addLog }) {
  const { robot, gripper, gaze_enabled, gaze } = state;
  const cam1Ref = useRef(null);

  useEffect(() => {
    const c = cam1Ref.current; if (!c) return;
    const ctx = c.getContext('2d');
    let raf;
    function frame() {
      ctx.fillStyle = '#060708'; ctx.fillRect(0, 0, c.width, c.height);
      for (let y = 0; y < c.height; y += 2) { ctx.fillStyle = 'rgba(255,255,255,0.01)'; ctx.fillRect(0, y, c.width, 1); }
      for (let i = 0; i < 28; i++) {
        ctx.fillStyle = `rgba(0,212,170,${Math.random() * 0.16})`;
        ctx.fillRect(Math.random() * c.width, Math.random() * c.height, 1, 1);
      }
      const bx = c.width/2 - 26 + Math.sin(Date.now()/450)*5, by = c.height/2 - 50;
      ctx.strokeStyle = 'rgba(0,212,170,.75)'; ctx.lineWidth = 1.2; ctx.strokeRect(bx, by, 52, 100);
      ctx.fillStyle = 'rgba(0,212,170,.8)'; ctx.font = '10px IBM Plex Mono,monospace';
      ctx.fillText('tube_blue 0.94', bx, by - 6);
      raf = requestAnimationFrame(frame);
    }
    frame();
    return () => cancelAnimationFrame(raf);
  }, []);

  const COORDS = [
    { axis: 'X', id: 'x', unit: 'mm' }, { axis: 'Y', id: 'y', unit: 'mm' }, { axis: 'Z', id: 'z', unit: 'mm' },
    { axis: 'RX', id: 'rx', unit: '°' }, { axis: 'RY', id: 'ry', unit: '°' }, { axis: 'RZ', id: 'rz', unit: '°' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

      {/* 왼쪽: 카메라 + 로봇 좌표 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-lbl">U20CAM — 그리퍼 카메라</div>
        <div className="cam-box">
          <div className="cam-hdr">
            <span className="cam-name">U20CAM · USB · 720P</span>
            <span className="cam-fps">30fps</span>
          </div>
          <div className="cam-feed" style={{ height: 180 }}>
            <canvas ref={cam1Ref} id="cam1" width={640} height={360} />
            <div className="cam-corner tl">YOLOv8 탐지</div>
            <div className="cam-corner br">tube_blue 0.94</div>
          </div>
        </div>

        <div className="section-lbl">로봇팔 좌표</div>
        <div className="card">
          <div className="card-title">위치 (mm)</div>
          <div className="coord-grid-6">
            {COORDS.slice(0, 3).map(({ axis, id, unit }) => (
              <div key={id} className="coord-cell">
                <div className="coord-axis">{axis}</div>
                <div className="coord-val">{Math.round(robot[id])}</div>
                <div className="coord-unit">{unit}</div>
              </div>
            ))}
          </div>
          <div className="card-title" style={{ marginTop: 4 }}>자세 (°)</div>
          <div className="coord-grid-6">
            {COORDS.slice(3).map(({ axis, id, unit }) => (
              <div key={id} className="coord-cell">
                <div className="coord-axis">{axis}</div>
                <div className="coord-val">{Math.round(robot[id])}</div>
                <div className="coord-unit">{unit}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 오른쪽: 제어 + 그리퍼 + 연결 상태 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-lbl">제어</div>
        <div className="card">
          <button className="estop-btn" onClick={triggerStop}>⬛ 긴급정지</button>
          <div className="hint">키보드 SPACE</div>
          <div className="btn2">
            {[['홈 복귀','home'],['상태 초기화','reset'],['재연결','reconnect'],['FSM 리셋','fsm']].map(([lbl, key]) => (
              <button key={key} className="ctrl-btn" onClick={() => addLog('info', lbl)}>{lbl}</button>
            ))}
          </div>
        </div>

        <div className="section-lbl">그리퍼</div>
        <div className="card">
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 12px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 5,
          }}>
            <span className="small-label">현재 상태</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 500, color: gripper === 'open' ? 'var(--teal)' : 'var(--amber)' }}>
              {gripper === 'open' ? '열림' : '닫힘 (집기 중)'}
            </span>
          </div>
          <div className="btn2">
            <button className="ctrl-btn" onClick={() => setGripper(true)}>열기</button>
            <button className="ctrl-btn on" onClick={() => setGripper(false)}>닫기 (집기)</button>
          </div>
          <div style={{ height: 1, background: 'var(--border)' }} />
          <button
            className={`ctrl-btn${gaze_enabled ? ' on' : ''}`}
            onClick={toggleGaze}
            style={{ padding: 11 }}
          >
            시선 제어 {gaze_enabled ? '활성화' : '비활성화'}
          </button>
        </div>

        <div className="section-lbl">연결 상태</div>
        <div className="card" style={{ padding: '10px 12px' }}>
          <div className="conn-list">
            {[
              ['myCobot Pi', 'ok', '● 연결'],
              ['C++ 소켓',   'ok', '● 연결'],
              ['OV9281',     'ok', '● 60fps'],
              ['U20CAM',     'ok', '● 30fps'],
              ['YOLOv8',     'warn','● 대기'],
            ].map(([name, cls, st]) => (
              <div key={name} className="conn-row">
                <span className="conn-name">{name}</span>
                <span className={`conn-st ${cls}`}>{st}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
