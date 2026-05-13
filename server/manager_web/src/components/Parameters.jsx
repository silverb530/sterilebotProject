import { useState } from "react";
import { C, Card, Btn, ParamRow, s } from "../styles";

const DEFAULTS = {
  ear:"0.20", ear_ms:"150", dwell:"1.5", dwell_r:"30", dbl:"0.5",
  safe_r:"260", safe_z:"200", grip_spd:"10", move_spd:"30",
};

export default function Parameters({ setStatus }) {
  const [p, setP] = useState({ ...DEFAULTS });
  const set = (k) => (e) => setP(prev => ({ ...prev, [k]: e.target.value }));

  const apply = () => {
    fetch("/api/params", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(p),
    }).then(() => setStatus("파라미터 적용됨"));
  };

  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        <Card title="시선 제어">
          <ParamRow name="EAR 임계값"    desc="이 값 이하 시 깜빡임으로 판정"      value={p.ear}    onChange={set("ear")}/>
          <ParamRow name="깜빡임 유지 시간" desc="EAR 임계값 이하 유지 최소 시간"   value={p.ear_ms} onChange={set("ear_ms")}  unit="ms"/>
          <ParamRow name="Dwell 시간"    desc="응시 유지 시간 → 로봇 이동 트리거" value={p.dwell}  onChange={set("dwell")}  unit="s"/>
          <ParamRow name="Dwell 반경"    desc="응시 중 허용되는 동공 이동 범위"    value={p.dwell_r} onChange={set("dwell_r")} unit="px"/>
          <ParamRow name="이중 깜빡임 간격" desc="이 시간 내 2회 → 긴급정지"      value={p.dbl}    onChange={set("dbl")}   unit="s"/>
          <div style={{ marginTop:12, padding:"10px 12px", background:`${C.accent}10`, borderRadius:C.r, fontSize:12, color:C.accent }}>
            ℹ 모든 파라미터는 실시간으로 적용됩니다.
          </div>
        </Card>

        <div style={s.col}>
          <Card title="로봇 안전">
            <ParamRow name="안전 반경"        desc="초과 시 이동 거부"         value={p.safe_r}   onChange={set("safe_r")}   unit="mm"/>
            <ParamRow name="수평 이동 안전 높이" desc="이동 시 유지할 Z값"       value={p.safe_z}   onChange={set("safe_z")}   unit="mm"/>
            <ParamRow name="집기 하강 속도"     desc="그리퍼 내려올 때 속도"     value={p.grip_spd} onChange={set("grip_spd")} unit="%"/>
            <ParamRow name="이동 속도"         desc="일반 수평 이동 속도"       value={p.move_spd} onChange={set("move_spd")} unit="%"/>
            <div style={{ marginTop:12, padding:"10px 12px", background:`${C.green}10`, borderRadius:C.r, fontSize:12, color:C.green }}>
              ✓ 안전 파라미터 변경 시 즉시 적용됩니다.
            </div>
          </Card>
          <div style={{ display:"flex", gap:8 }}>
            <Btn style={{ flex:1 }} onClick={() => { setP({ ...DEFAULTS }); setStatus("기본값 복원"); }}>기본값</Btn>
            <Btn primary style={{ flex:1 }} onClick={apply}>적용</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}
