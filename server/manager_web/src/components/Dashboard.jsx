import { C, Card, Badge, CamBox, ConnRow, s } from "../styles";

function MetricBar({ label, value, pct, color }) {
  return (
    <div style={{ marginTop:8 }}>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
        <span style={{ fontSize:11, color:C.textDim }}>{label}</span>
        <span style={{ fontSize:11, color, fontFamily:C.mono }}>{value}</span>
      </div>
      <div style={{ height:4, background:C.border, borderRadius:2, overflow:"hidden" }}>
        <div style={{ height:"100%", width:`${pct}%`, background:color, borderRadius:2, transition:"width .4s" }}/>
      </div>
    </div>
  );
}

function StatCell({ label, value, color, unit }) {
  return (
    <div style={{
      background:C.surface2, border:`1px solid ${C.border}`,
      borderRadius:C.r, padding:"10px 12px",
    }}>
      <div style={{ fontSize:11, color:C.textDim, marginBottom:4 }}>{label}</div>
      <div style={{ fontFamily:C.mono, fontSize:20, fontWeight:700, color: color||C.text }}>{value}</div>
      {unit && <div style={{ fontSize:10, color:C.textDim }}>{unit}</div>}
    </div>
  );
}

export default function Dashboard({ setStatus }) {
  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        {/* 좌측: 카메라 3대 */}
        <div style={s.col}>
          <Card title="카메라 1 — 시선 추적" badge={<Badge type="ok">OV9281 · 60fps</Badge>}>
            <div style={{ padding:0, margin:"-12px -14px -12px" }}>
              <CamBox label="CAM1" sub="640×480" fps="60 fps" height={140} icon="👁" msg="동공 추적 대기 중..."/>
            </div>
          </Card>
          <Card title="카메라 2 — 작업 영역" badge={<Badge type="ok">OV9281 · 60fps</Badge>}>
            <div style={{ padding:0, margin:"-12px -14px -12px" }}>
              <CamBox label="CAM2" sub="640×480" fps="60 fps" height={140} icon="📷" msg="작업 영역 스트림 대기 중..."/>
            </div>
          </Card>
          <Card title="카메라 3 — 로봇 암" badge={<Badge type="warn">대기</Badge>}>
            <div style={{ padding:0, margin:"-12px -14px -12px" }}>
              <CamBox label="CAM3" sub="640×480" height={140} icon="🦾" msg="로봇 암 스트림 대기 중..."/>
            </div>
          </Card>
        </div>

        {/* 우측: 지표 + 연결 */}
        <div style={s.col}>
          <Card title="학습 성능 지표">
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr", gap:8, marginBottom:10 }}>
              <StatCell label="학습률 (LR)"  value="0.001" color={C.accent}/>
              <StatCell label="오차율 (Loss)" value="0.023" color={C.green}/>
              <StatCell label="평균 오차" value="—" color={C.textDim} unit="mm"/>
              <StatCell label="최대 오차" value="—" color={C.textDim} unit="mm"/>
            </div>
            <MetricBar label="학습률 진행" value="0.001" pct={65} color={C.accent}/>
            <MetricBar label="오차율 감소" value="0.023" pct={85} color={C.green}/>
          </Card>

          <Card title="연결 상태">
            <div style={{ padding:"0 0" }}>
              <ConnRow name="myCobot Pi"  badge={<Badge type="ok">● 연결됨</Badge>}/>
              <ConnRow name="C++ 소켓"    badge={<Badge type="ok">● 연결됨</Badge>}/>
              <ConnRow name="OV9281 ×3"  badge={<Badge type="ok">● 60fps</Badge>}/>
              <ConnRow name="Gaze CNN"   badge={<Badge type="warn">대기</Badge>}/>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
