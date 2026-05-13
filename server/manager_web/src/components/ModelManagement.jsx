import { useEffect, useRef } from "react";
import { C, Card, Badge, Btn, s } from "../styles";

function genDecay(n, s, e) {
  return Array.from({ length:n }, (_, i) => +(s * Math.pow(e/s, i/(n-1))).toFixed(6));
}
function genLoss(n) {
  return Array.from({ length:n }, (_, i) => +(0.5 * Math.exp(-3*i/n) + Math.random()*.02).toFixed(4));
}
function genGrowth(n) {
  return Array.from({ length:n }, (_, i) => +(0.89*(1-Math.exp(-4*i/n)) + Math.random()*.02).toFixed(4));
}

function TrainChart({ id, label2, data2, color2 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !window.Chart) return;
    const n = 50;
    const lr = genDecay(n, 0.01, 0.001);
    const chart = new window.Chart(ref.current, {
      type: "line",
      data: {
        labels: Array.from({ length:n }, (_, i) => i+1),
        datasets: [
          { label:"학습률", data:lr, borderColor:C.accent, borderWidth:1.5, pointRadius:0, yAxisID:"y1" },
          { label:label2, data:data2(n), borderColor:color2, borderWidth:1.5, pointRadius:0, yAxisID:"y2" },
        ],
      },
      options: {
        responsive:true, maintainAspectRatio:false, animation:false,
        plugins:{ legend:{ labels:{ font:{size:10}, boxWidth:12 } } },
        scales:{
          y1:{ type:"linear", position:"left", ticks:{font:{size:9}} },
          y2:{ type:"linear", position:"right", ticks:{font:{size:9}} },
        },
      },
    });
    return () => chart.destroy();
  }, []);
  return (
    <div style={{ height:180, background:C.surface2, border:`1px solid ${C.border}`, borderRadius:C.r, padding:10 }}>
      <canvas ref={ref}/>
    </div>
  );
}

export default function ModelManagement({ setStatus }) {
  return (
    <div style={{ height:"100%", overflowY:"auto", padding:14 }}>
      <div style={{ ...s.row2, alignItems:"start" }}>

        {/* Gaze CNN */}
        <Card
          title="Gaze CNN"
          badge={<Badge type="ok">로드됨</Badge>}
        >
          <div style={{ fontSize:12, color:C.textDim, marginBottom:4 }}>동공 좌표 → 로봇 좌표 변환 (ONNX Runtime)</div>
          <div style={{ fontFamily:C.mono, fontSize:12, color:C.textDim, marginBottom:12 }}>gaze.onnx</div>
          <TrainChart id="cnn" label2="오차율" data2={genLoss} color2="#EF4444"/>
          <div style={{ display:"flex", gap:8, marginTop:10 }}>
            <Btn primary style={{ flex:1 }} onClick={() => { setStatus("CNN 재학습 요청..."); alert("CNN 재학습 시작"); }}>CNN 재학습</Btn>
            <Btn style={{ flex:1 }} onClick={() => { setStatus("ONNX 내보내기"); alert("gaze.onnx 내보내기"); }}>ONNX 내보내기</Btn>
          </div>
        </Card>

        {/* YOLOv8 */}
        <Card
          title="YOLOv8"
          badge={<Badge type="warn">미로드</Badge>}
        >
          <div style={{ fontSize:12, color:C.textDim, marginBottom:4 }}>시험관/비커 탐지 + 집기 위치 보정</div>
          <div style={{ fontFamily:C.mono, fontSize:12, color:C.textDim, marginBottom:12 }}>미지정</div>
          <TrainChart id="yolo" label2="mAP50" data2={genGrowth} color2="#F59E0B"/>
          <div style={{ display:"flex", gap:8, marginTop:10 }}>
            <Btn style={{ flex:1 }} onClick={() => window.open("https://app.roboflow.com","_blank")}>Roboflow 라벨링</Btn>
            <Btn primary style={{ flex:1 }} onClick={() => window.open("https://colab.research.google.com","_blank")}>Google Colab 학습</Btn>
          </div>
        </Card>
      </div>
    </div>
  );
}
