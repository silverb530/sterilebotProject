import { useState, useRef } from "react";
import { C, Card, Badge, Btn, s } from "../styles";

function SliderRow({ label, id, min, max, value, onInput, unit }) {
  return (
    <div style={{ marginBottom:14 }}>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5 }}>
        <span style={{ fontFamily:C.mono, fontSize:11, fontWeight:600, color:C.textDim }}>{label}</span>
        <span style={{ fontFamily:C.mono, fontSize:13, fontWeight:700 }}>{value} {unit}</span>
      </div>
      <input type="range" min={min} max={max} value={value} onChange={onInput}
        style={{ width:"100%", accentColor:C.accent, cursor:"pointer" }}/>
    </div>
  );
}

export default function ManualControl({ setStatus }) {
  const [coords, setCoords] = useState({ x:135, y:-82, z:200, rz:0 });
  const [sliders, setSliders] = useState({ x:135, y:-82, z:200, rz:0 });
  const [gripper, setGripper] = useState("open");
  const [log, setLog] = useState("$ 대기 중...");
  const logRef = useRef(null);

  const appendLog = (msg) => {
    const t = new Date().toTimeString().slice(0,8);
    setLog(prev => prev + `\n[${t}] ${msg}`);
    setTimeout(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, 50);
  };

  const sendCoords = (c) => {
    fetch("/api/robot/move", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(c),
    }).then(r => r.json()).then(d => {
      const msg = d.ok
        ? `이동 → X:${c.x} Y:${c.y} Z:${c.z} RZ:${c.rz}`
        : `[오류] ${d.msg}`;
      appendLog(msg);
      setStatus(d.ok ? "이동 실행" : d.msg);
    });
  };

  const goHome = () => {
    const home = { x:135, y:-82, z:200, rz:0 };
    fetch("/api/robot/home", { method:"POST" }).then(() => {
      setCoords(home); setSliders(home);
      appendLog("홈 복귀"); setStatus("홈 복귀");
    });
  };

  const setGrip = (action) => {
    fetch(`/api/gripper/${action}`, { method:"POST" }).then(() => {
      setGripper(action);
      appendLog(`그리퍼 ${action==="open"?"열기":"닫기"}`);
    });
  };

  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        {/* 좌측 */}
        <div style={s.col}>
          <Card title="좌표 직접 입력">
            <div style={{ display:"grid", gridTemplateColumns:"36px 1fr", gap:"6px 10px", alignItems:"center", marginBottom:12 }}>
              {["x","y","z","rz"].map(k => (
                <>
                  <span key={k+"l"} style={{ fontFamily:C.mono, fontSize:12, fontWeight:600, color:C.textDim }}>
                    {k.toUpperCase()}
                  </span>
                  <input key={k+"i"} type="number" value={coords[k]}
                    onChange={e => setCoords(p => ({ ...p, [k]: +e.target.value }))}
                    style={{
                      height:32, padding:"0 10px",
                      border:`1px solid ${C.border2}`, borderRadius:C.r,
                      fontFamily:C.mono, fontSize:13, background:C.surface, width:"100%",
                    }}/>
                </>
              ))}
            </div>
            <div style={{ display:"flex", gap:8 }}>
              <Btn primary onClick={() => sendCoords(coords)} style={{ flex:1 }}>이동 실행</Btn>
              <Btn onClick={goHome} style={{ flex:1 }}>홈 복귀</Btn>
            </div>
          </Card>

          <Card
            title="그리퍼"
            badge={<Badge type={gripper==="open"?"ok":"warn"}>{gripper==="open"?"열림":"닫힘"}</Badge>}
          >
            <div style={{ display:"flex", gap:8 }}>
              <Btn onClick={() => setGrip("open")} style={{ flex:1 }}>열기 (0)</Btn>
              <Btn primary onClick={() => setGrip("close")} style={{ flex:1 }}>닫기 (100)</Btn>
            </div>
          </Card>
        </div>

        {/* 우측 */}
        <div style={s.col}>
          <Card title="축별 슬라이더">
            <SliderRow label="X" min={-260} max={260} value={sliders.x} unit="mm"
              onInput={e => setSliders(p=>({...p, x:+e.target.value}))}/>
            <SliderRow label="Y" min={-260} max={260} value={sliders.y} unit="mm"
              onInput={e => setSliders(p=>({...p, y:+e.target.value}))}/>
            <SliderRow label="Z" min={50} max={300} value={sliders.z} unit="mm"
              onInput={e => setSliders(p=>({...p, z:+e.target.value}))}/>
            <SliderRow label="RZ" min={-180} max={180} value={sliders.rz} unit="°"
              onInput={e => setSliders(p=>({...p, rz:+e.target.value}))}/>
            <Btn primary style={{ width:"100%" }}
              onClick={() => { setCoords(sliders); sendCoords(sliders); }}>
              슬라이더 값으로 이동
            </Btn>
          </Card>

          <Card
            title="명령 로그"
            action={<Btn small onClick={() => setLog("$ 대기 중...")}>지우기</Btn>}
          >
            <div ref={logRef} style={{
              background:"#0C111D", borderRadius:C.r,
              padding:"10px 12px", minHeight:120, maxHeight:200,
              overflowY:"auto", fontFamily:C.mono, fontSize:12,
              color:"#D0D5DD", lineHeight:1.8, whiteSpace:"pre-wrap",
              margin:"-12px -14px -12px",
            }}>
              {log}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
