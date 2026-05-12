import { useEffect, useRef } from 'react';

export default function GazeTab({ state, triggerStop }) {
  const { ear, gaze, dwell } = state;
  const cam0Ref = useRef(null);
  const blink = ear < 0.20;

  const px = ((gaze.cx - 160) / (1120 - 160) * 100).toFixed(1) + '%';
  const py = ((gaze.cy - 80)  / (720  - 80)  * 100).toFixed(1) + '%';

  // 카메라 캔버스 렌더링
  useEffect(() => {
    const c = cam0Ref.current; if (!c) return;
    const ctx = c.getContext('2d');
    let raf;
    function frame() {
      ctx.fillStyle = '#060708'; ctx.fillRect(0, 0, c.width, c.height);
      for (let y = 0; y < c.height; y += 2) { ctx.fillStyle = 'rgba(255,255,255,0.01)'; ctx.fillRect(0, y, c.width, 1); }
      for (let i = 0; i < 28; i++) {
        ctx.fillStyle = `rgba(60,180,255,${Math.random() * 0.16})`;
        ctx.fillRect(Math.random() * c.width, Math.random() * c.height, 1, 1);
      }
      ctx.strokeStyle = 'rgba(60,180,255,.22)'; ctx.lineWidth = 0.5;
      ctx.beginPath(); ctx.moveTo(c.width/2-14, c.height/2); ctx.lineTo(c.width/2+14, c.height/2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(c.width/2, c.height/2-10); ctx.lineTo(c.width/2, c.height/2+10); ctx.stroke();
      const sx = (gaze.cx-160)/(1120-160)*c.width, sy = (gaze.cy-80)/(720-80)*c.height;
      ctx.strokeStyle = 'rgba(80,200,255,.6)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(sx, sy, 14, 0, Math.PI*2); ctx.stroke();
      ctx.fillStyle = 'rgba(80,200,255,.5)'; ctx.beginPath(); ctx.arc(sx, sy, 3, 0, Math.PI*2); ctx.fill();
      raf = requestAnimationFrame(frame);
    }
    frame();
    return () => cancelAnimationFrame(raf);
  }, [gaze]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

      {/* 왼쪽: OV9281 카메라 + 시선 맵 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-lbl">OV9281 — 동공 카메라</div>
        <div className="cam-box" style={{ flex: 1 }}>
          <div className="cam-hdr">
            <span className="cam-name">OV9281 IR NoIR · CSI</span>
            <span className="cam-fps">60fps</span>
          </div>
          <div className="cam-feed" style={{ height: 180 }}>
            <canvas ref={cam0Ref} id="cam0" width={640} height={400} />
            <div className="cam-corner tl">1280×800 · MIPI</div>
            <div className="cam-corner br">cx:{gaze.cx} cy:{gaze.cy}</div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">시선 위치 맵</div>
          <div style={{
            width: '100%', aspectRatio: '4/3', background: '#070809',
            borderRadius: 5, border: '1px solid var(--border)',
            position: 'relative', overflow: 'hidden',
          }}>
            <div style={{ position: 'absolute', background: '#ffffff10', width: '100%', height: 1, top: '50%' }} />
            <div style={{ position: 'absolute', background: '#ffffff10', height: '100%', width: 1, left: '50%' }} />
            <div style={{
              position: 'absolute', width: 24, height: 24, borderRadius: '50%',
              border: '1px solid var(--teal)', opacity: 0.3,
              transform: 'translate(-50%,-50%)', transition: 'left .08s, top .08s',
              left: px, top: py,
            }} />
            <div style={{
              position: 'absolute', width: 10, height: 10, borderRadius: '50%',
              background: 'var(--teal)', boxShadow: '0 0 8px var(--teal)',
              transform: 'translate(-50%,-50%)', transition: 'left .08s, top .08s',
              left: px, top: py,
            }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
            {[['cx (px)', gaze.cx], ['cy (px)', gaze.cy], ['→ X (mm)', gaze.rx], ['→ Y (mm)', gaze.ry]].map(([axis, val]) => (
              <div key={axis} style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 5, padding: '8px 10px' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)', marginBottom: 3 }}>{axis}</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 500 }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 오른쪽: EAR + Dwell + 긴급정지 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-lbl">EAR — 눈 깜빡임</div>
        <div className="card">
          <div className="card-title">눈 종횡비 (Eye Aspect Ratio)</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 44, fontWeight: 500, lineHeight: 1, color: blink ? 'var(--red)' : 'var(--teal)' }}>
            {ear.toFixed(2)}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
            <span className="small-label">0.00</span>
            <span className="small-label" style={{ color: 'var(--red)' }}>임계값 0.20</span>
            <span className="small-label">0.50</span>
          </div>
          <div style={{ height: 8, background: 'var(--surface2)', borderRadius: 4, position: 'relative', overflow: 'visible' }}>
            <div style={{
              height: '100%', borderRadius: 4, transition: 'width .1s, background .2s',
              width: `${ear / 0.5 * 100}%`,
              background: blink ? 'var(--red)' : 'var(--teal)',
            }} />
            <div style={{ position: 'absolute', top: -4, left: '40%', width: 2, height: 16, background: 'var(--red)', borderRadius: 1 }} />
          </div>
          <div className="small-label" style={{ marginTop: 6 }}>
            {blink ? '⚠ 깜빡임 감지 — 그리퍼 닫기' : '정상 — 깜빡임 없음'}
          </div>
        </div>

        <div className="section-lbl">DWELL — 응시 유지</div>
        <div className="card">
          <div className="card-title">응시 지속 시간 (목표 1.5s)</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 36, fontWeight: 500, color: 'var(--amber)' }}>
              {Math.round(dwell)}
            </span>
            <span className="small-label">% (1.5s = 100%)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }} className="small-label">
            <span>0s</span><span>0.75s</span><span>1.5s ✓</span>
          </div>
          <div style={{ height: 10, background: 'var(--surface2)', borderRadius: 5, overflow: 'hidden', marginTop: 4 }}>
            <div style={{ height: '100%', background: 'var(--amber)', borderRadius: 5, transition: 'width .05s', width: `${dwell}%` }} />
          </div>
          <div className="small-label" style={{ marginTop: 6 }}>
            {dwell > 0 ? `응시 중... ${(dwell / 100 * 1.5).toFixed(1)}s` : '대기 중'}
          </div>
        </div>

        <div className="section-lbl">긴급정지</div>
        <div className="card">
          <button className="estop-btn" onClick={triggerStop}>⬛ 긴급정지</button>
          <div className="hint">키보드 SPACE · 이중 깜빡임 (0.5s 내 2회)</div>
        </div>
      </div>
    </div>
  );
}
