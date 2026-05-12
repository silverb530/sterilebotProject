import { useEffect, useRef } from 'react';

export default function OverviewTab() {
  const cam2Ref = useRef(null);

  useEffect(() => {
    const c = cam2Ref.current; if (!c) return;
    const ctx = c.getContext('2d');
    const rects = [
      { x: c.width*.12, y: c.height*.25, w: c.width*.14, h: c.height*.45, lbl: '거치대' },
      { x: c.width*.42, y: c.height*.35, w: c.width*.12, h: c.height*.3,  lbl: '비커' },
      { x: c.width*.7,  y: c.height*.28, w: c.width*.12, h: c.height*.42, lbl: '깔때기' },
    ];
    let raf;
    function frame() {
      ctx.fillStyle = '#060708'; ctx.fillRect(0, 0, c.width, c.height);
      for (let y = 0; y < c.height; y += 2) { ctx.fillStyle = 'rgba(255,255,255,0.01)'; ctx.fillRect(0, y, c.width, 1); }
      for (let i = 0; i < 35; i++) {
        ctx.fillStyle = `rgba(200,200,200,${Math.random()*.1})`;
        ctx.fillRect(Math.random()*c.width, Math.random()*c.height, 1, 1);
      }
      rects.forEach(r => {
        ctx.strokeStyle = 'rgba(200,200,200,.4)'; ctx.lineWidth = 1; ctx.strokeRect(r.x, r.y, r.w, r.h);
        ctx.fillStyle = 'rgba(200,200,200,.5)'; ctx.font = '10px IBM Plex Mono,monospace';
        ctx.fillText(r.lbl, r.x+2, r.y-4);
      });
      raf = requestAnimationFrame(frame);
    }
    frame();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
      <div className="section-lbl">C920 — 작업대 조감 (60cm 폴대 고정)</div>
      <div className="cam-box" style={{ flex: 1 }}>
        <div className="cam-hdr">
          <span className="cam-name">Logitech C920 · USB · 1080P</span>
          <span className="cam-fps">30fps</span>
        </div>
        <div className="cam-feed" style={{ flex: 1, minHeight: 300 }}>
          <canvas ref={cam2Ref} id="cam2" width={960} height={540} />
          <div className="cam-corner tl">작업대 전체 조감</div>
          <div className="cam-corner br">보조 카메라</div>
        </div>
      </div>
    </div>
  );
}
