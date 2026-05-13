import { useState, useCallback } from "react";
import { C, Card, Badge, CamBox, Btn, ProgressBar, s } from "../styles";

const TOTAL = 16;

export default function Calibration({ setStatus }) {
  const [step,    setStep]    = useState(0);
  const [running, setRunning] = useState(false);
  const [done,    setDone]    = useState(false);
  const [avgErr,  setAvgErr]  = useState(null);
  const [maxErr,  setMaxErr]  = useState(null);
  const [msg,     setMsg]     = useState("'캘리브레이션 시작' 버튼을 누른 후\n마커를 순서대로 클릭해 3초씩 응시하세요.");

  const start = useCallback(() => {
    fetch("/api/calib/start", { method:"POST" })
      .then(r => r.json())
      .then(() => {
        setStep(0); setRunning(true); setDone(false);
        setAvgErr(null); setMaxErr(null);
        setMsg("마커 1번을 3초간 응시해 주세요.");
        setStatus("캘리브레이션 시작");
      });
  }, [setStatus]);

  const reset = useCallback(() => {
    fetch("/api/calib/reset", { method:"POST" })
      .then(r => r.json())
      .then(() => {
        setStep(0); setRunning(false); setDone(false);
        setAvgErr(null); setMaxErr(null);
        setMsg("'캘리브레이션 시작' 버튼을 누른 후\n마커를 순서대로 클릭해 3초씩 응시하세요.");
        setStatus("초기화됨");
      });
  }, [setStatus]);

  const clickMarker = useCallback((idx) => {
    if (!running || idx !== step) return;
    fetch(`/api/calib/click/${idx}`, { method:"POST" })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) return;
        setStep(d.step);
        if (d.done) {
          setRunning(false); setDone(true);
          setAvgErr(d.avg_err); setMaxErr(d.max_err);
          setMsg("✓ 완료! 모델 관리에서 CNN 학습을 진행하세요.");
          setStatus("캘리브레이션 완료");
        } else {
          setMsg(`마커 ${d.step + 1}번을 3초간 응시해 주세요.`);
        }
      });
  }, [running, step, setStatus]);

  const badgeType = done ? "ok" : running ? "info" : "warn";
  const badgeText = done ? "완료" : running ? "진행 중" : "진행 전";

  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        {/* 좌측: 마커 그리드 + 측정결과 */}
        <div style={s.col}>
          <Card
            title="마커 그리드 (4 × 4)"
            badge={<Badge type={badgeType}>{badgeText}</Badge>}
          >
            <ProgressBar value={step} max={TOTAL}/>
            {/* 마커 그리드 */}
            <div style={{
              display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:6,
              padding:14, background:C.surface2,
              border:`1px solid ${C.border}`, borderRadius:C.r,
              marginTop:12,
            }}>
              {Array.from({ length:TOTAL }, (_, i) => {
                const isDone    = i < step;
                const isNext    = i === step && running;
                return (
                  <button
                    key={i}
                    onClick={() => clickMarker(i)}
                    style={{
                      aspectRatio:"1", border:`1.5px solid ${isDone ? C.accent : isNext ? C.accent : C.border2}`,
                      borderRadius:6, background: isDone ? C.accent : isNext ? `${C.accent}15` : C.surface,
                      cursor: running && i === step ? "pointer" : "default",
                      fontSize:13, fontWeight:600,
                      color: isDone ? "#fff" : C.textDim,
                      fontFamily:C.mono,
                      animation: isNext ? "pulse 1s infinite" : "none",
                      transition:"all .15s",
                    }}
                  >{i+1}</button>
                );
              })}
            </div>
          </Card>

          <Card title="측정 결과">
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:8 }}>
              {[
                { label:"평균 오차", value: avgErr ?? "—", unit:"mm", color: avgErr ? C.green : C.textDim },
                { label:"최대 오차", value: maxErr ?? "—", unit:"mm", color: maxErr ? C.green : C.textDim },
                { label:"허용 기준", value:"15", unit:"mm 이하", color:C.amber, bg:`${C.amber}15`, border:C.amber },
              ].map(({ label, value, unit, color, bg, border }) => (
                <div key={label} style={{
                  background: bg||C.surface2, border:`1px solid ${border||C.border}`,
                  borderRadius:C.r, padding:"10px 12px",
                }}>
                  <div style={{ fontSize:11, color: border?color:C.textDim, marginBottom:4 }}>{label}</div>
                  <div style={{ fontFamily:C.mono, fontSize:24, fontWeight:700, color }}>{value}</div>
                  <div style={{ fontSize:10, color }}>{unit}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* 우측: 카메라 뷰 + 진행 안내 */}
        <div style={s.col}>
          <Card title="카메라 뷰">
            <div style={{ margin:"-12px -14px -12px" }}>
              <CamBox height={160} icon="👁" msg="실시간 동공 추적"/>
            </div>
          </Card>

          <Card title="진행 안내">
            <div style={{
              fontSize:12, color:C.textMid,
              background:C.surface2, border:`1px solid ${C.border}`,
              borderRadius:C.r, padding:10, lineHeight:1.7,
              marginBottom:10, whiteSpace:"pre-line",
            }}>
              {msg}
            </div>
            <div style={{ display:"flex", gap:8 }}>
              <Btn primary onClick={start} style={{ flex:1 }}>▶ 시작</Btn>
              <Btn onClick={reset} style={{ flex:1 }}>↺ 초기화</Btn>
            </div>
          </Card>
        </div>
      </div>

      <style>{`@keyframes pulse{0%,100%{box-shadow:0 0 0 0 ${C.accent}30;}50%{box-shadow:0 0 0 5px ${C.accent}10;}}`}</style>
    </div>
  );
}
