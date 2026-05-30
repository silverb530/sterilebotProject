import { useState, useEffect, useRef } from "react";
import { C } from "../styles";

function Badge({ type, children }) {
  const colors = { ok:{bg:C.greenDim,c:C.green}, warn:{bg:C.amberDim,c:C.amber}, err:{bg:C.redDim,c:C.red}, info:{bg:C.accentDim,c:C.accent} };
  const cl = colors[type] || colors.info;
  return <span style={{ display:"inline-flex", padding:"2px 10px", borderRadius:20, fontSize:11, fontWeight:500, background:cl.bg, color:cl.c }}>{children}</span>;
}
function Btn({ children, primary, danger, small, onClick, disabled, style={} }) {
  return <button onClick={onClick} disabled={disabled} style={{ height:small?26:32, padding:small?"0 10px":"0 14px", background:primary?C.accent:danger?C.redDim:C.surface, border:`1px solid ${primary?C.accent:danger?C.red:C.border2}`, borderRadius:6, fontSize:small?11:12, color:primary?"#fff":danger?C.red:C.textMid, fontWeight:primary?500:400, cursor:disabled?"not-allowed":"pointer", opacity:disabled?0.5:1, display:"inline-flex", alignItems:"center", gap:6, ...style }}>{children}</button>;
}

// ── 10초 영상 촬영 얼굴 등록 모달 ───────────────────────────────
function FaceRegisterModal({ researcher, onClose, onDone }) {
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const streamRef  = useRef(null);
  const timerRef   = useRef(null);
  const captureRef = useRef(null);

  // step: ready | preview | recording | uploading | done | error
  const [step, setStep]         = useState("ready");
  const [countdown, setCountdown] = useState(10);      // 녹화 카운트다운
  const [captured, setCaptured] = useState([]);        // 캡처된 프레임 base64 목록
  const [uploadIdx, setUploadIdx] = useState(0);       // 업로드 진행 인덱스
  const [uploaded, setUploaded] = useState(0);         // 업로드 완료 수
  const [msg, setMsg]           = useState("");

  // 카메라 시작
  useEffect(() => {
    let active = true;
    navigator.mediaDevices.getUserMedia({ video: { width:640, height:480, facingMode:"user" } })
      .then(stream => {
        if (!active) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        setStep("preview");
      })
      .catch(() => { setStep("error"); setMsg("카메라 접근 권한이 없습니다."); });
    return () => {
      active = false;
      clearInterval(timerRef.current);
      clearInterval(captureRef.current);
      streamRef.current?.getTracks().forEach(t => t.stop());
    };
  }, []);

  // 녹화 시작
  const startRecording = () => {
    setStep("recording");
    setCountdown(10);
    setCaptured([]);

    let remaining = 10;
    const frames = [];

    // 카운트다운 타이머 (1초마다)
    timerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(timerRef.current);
        clearInterval(captureRef.current);
        uploadFrames(frames);
      }
    }, 1000);

    // 캡처 타이머 (0.5초마다 → 10초 = 20장)
    // 첫 프레임 즉시 캡처 (0ms)
    const captureFrame = () => {
      const video  = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas) {
        canvas.width  = video.videoWidth  || 640;
        canvas.height = video.videoHeight || 480;
        canvas.getContext("2d").drawImage(video, 0, 0);
        frames.push(canvas.toDataURL("image/jpeg", 0.9));
        setCaptured([...frames]);
      }
    };
    captureFrame();
    captureRef.current = setInterval(captureFrame, 500);
  };

  // 프레임들 순서대로 Flask 업로드
  const uploadFrames = async (frames) => {
    setStep("uploading");
    setUploadIdx(0);
    setUploaded(0);

    let successCount = 0;
    for (let i = 0; i < frames.length; i++) {
      setUploadIdx(i + 1);
      try {
        const blob = await (await fetch(frames[i])).blob();
        const url = `/api/researchers/${researcher.id}/face` + (i === 0 ? "?reset=true" : "");
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "image/jpeg" },
          body: blob,
        });
        const data = await resp.json();
        if (resp.ok && data.ok) {
          successCount++;
          setUploaded(successCount);
          onDone();
        }
      } catch {
        // 개별 프레임 실패는 무시하고 계속
      }
      // 프레임 간 간격
      await new Promise(r => setTimeout(r, 200));
    }

    if (successCount > 0) {
      setStep("done");
      setMsg(`${successCount}개 벡터 등록 완료!`);
    } else {
      setStep("error");
      setMsg("얼굴 등록에 실패했습니다. 다시 시도해 주세요.");
    }
  };

  const retry = () => {
    setCaptured([]);
    setUploaded(0);
    setUploadIdx(0);
    setStep("preview");
  };

  // 진행률
  const uploadProgress = captured.length > 0 ? (uploaded / captured.length) * 100 : 0;

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,.55)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000 }}>
      <div style={{ background:C.surface, borderRadius:10, boxShadow:"0 16px 48px rgba(0,0,0,.25)", width:540, overflow:"hidden" }}>

        {/* 헤더 */}
        <div style={{ padding:"14px 18px", borderBottom:`1px solid ${C.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div>
            <div style={{ fontSize:15, fontWeight:600 }}>얼굴 등록 — 10초 영상 촬영</div>
            <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{researcher.name} 연구원</div>
          </div>
          <button onClick={onClose} disabled={step === "recording" || step === "uploading"}
            style={{ width:28, height:28, border:"none", background:"transparent", borderRadius:4,
                     cursor: step === "recording" || step === "uploading" ? "not-allowed" : "pointer",
                     fontSize:16, color: step === "recording" || step === "uploading" ? "#ccc" : C.textDim }}>✕</button>
        </div>

        {/* 카메라 영역 */}
        <div style={{ position:"relative", background:"#111", height:300 }}>
          <video ref={videoRef} autoPlay playsInline muted
            style={{ width:"100%", height:"100%", objectFit:"cover" }}/>

          {/* 카운트다운 오버레이 */}
          {step === "recording" && (
            <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", pointerEvents:"none" }}>
              {/* 카운트다운 원 */}
              <div style={{ width:100, height:100, borderRadius:"50%", background:"rgba(0,0,0,.6)", border:"4px solid #EF4444", display:"flex", alignItems:"center", justifyContent:"center", marginBottom:12 }}>
                <span style={{ color:"#fff", fontSize:48, fontWeight:700 }}>{countdown}</span>
              </div>
              <div style={{ background:"rgba(239,68,68,.9)", borderRadius:6, padding:"4px 14px" }}>
                <span style={{ color:"#fff", fontSize:13, fontWeight:600 }}>● 녹화 중 — 자연스럽게 움직여 주세요</span>
              </div>
              {/* 캡처 수 */}
              <div style={{ marginTop:10, color:"#fff", fontSize:12, opacity:0.8 }}>
                {captured.length}장 캡처됨
              </div>
            </div>
          )}

          {/* 업로드 중 오버레이 */}
          {step === "uploading" && (
            <div style={{ position:"absolute", inset:0, background:"rgba(0,0,0,.7)", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:14 }}>
              <div style={{ width:36, height:36, border:"3px solid #fff3", borderTop:"3px solid #fff", borderRadius:"50%", animation:"spin 0.8s linear infinite" }}/>
              <div style={{ color:"#fff", fontSize:14, fontWeight:600 }}>벡터 추출 중... ({uploadIdx}/{captured.length})</div>
              {/* 업로드 진행바 */}
              <div style={{ width:240, height:6, background:"#fff3", borderRadius:3 }}>
                <div style={{ height:6, width:`${uploadProgress}%`, background:"#22C55E", borderRadius:3, transition:"width 0.3s" }}/>
              </div>
              <div style={{ color:"#22C55E", fontSize:12 }}>{uploaded}개 등록 완료</div>
            </div>
          )}

          {/* 완료 오버레이 */}
          {step === "done" && (
            <div style={{ position:"absolute", inset:0, background:"rgba(22,163,74,.3)", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:12 }}>
              <div style={{ fontSize:52 }}>✅</div>
              <div style={{ background:"#15803D", borderRadius:8, padding:"10px 28px", color:"#fff", fontSize:16, fontWeight:700 }}>{msg}</div>
              <div style={{ color:"#fff", fontSize:12 }}>인식률이 크게 향상되었습니다!</div>
            </div>
          )}

          {/* 에러 오버레이 */}
          {step === "error" && (
            <div style={{ position:"absolute", inset:0, background:"rgba(0,0,0,.65)", display:"flex", alignItems:"center", justifyContent:"center", padding:20 }}>
              <div style={{ color:"#F87171", fontSize:13, textAlign:"center" }}>⚠ {msg}</div>
            </div>
          )}

          {/* preview 브라켓 가이드 */}
          {step === "preview" && (
            <svg style={{ position:"absolute", inset:0, width:"100%", height:"100%", pointerEvents:"none" }} viewBox="0 0 640 300">
              <polyline points="200,60 200,100" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="200,60 240,60"  stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="440,60 440,100" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="400,60 440,60"  stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="200,240 200,200" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="200,240 240,240" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="440,240 440,200" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
              <polyline points="400,240 440,240" stroke="#22C55E" strokeWidth="3" fill="none" strokeLinecap="round"/>
            </svg>
          )}
        </div>

        <canvas ref={canvasRef} style={{ display:"none" }}/>

        {/* 안내 텍스트 */}
        <div style={{ padding:"10px 18px 4px", textAlign:"center", fontSize:12, color:C.textDim, minHeight:22 }}>
          {step === "preview"   && "녹화 시작 후 10초간 얼굴을 자연스럽게 움직여 주세요 — 0.5초마다 자동 캡처 (최대 20장)"}
          {step === "recording" && "얼굴을 천천히 좌우, 위아래로 움직여 주세요!"}
          {step === "uploading" && `${captured.length}개 프레임을 순서대로 서버에 전송 중입니다...`}
        </div>

        {/* 버튼 */}
        <div style={{ padding:"8px 18px 16px", display:"flex", gap:8, justifyContent:"flex-end" }}>
          {step === "preview"   && <Btn primary onClick={startRecording}>🎬 녹화 시작 (10초)</Btn>}
          {step === "done"      && <Btn primary onClick={onClose}>✓ 완료</Btn>}
          {step === "error"     && <><Btn onClick={onClose}>닫기</Btn><Btn primary onClick={retry}>다시 시도</Btn></>}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── 메인 연구원 목록 ─────────────────────────────────────────────
export default function Researchers() {
  const [list, setList]           = useState([]);
  const [modal, setModal]         = useState(null);
  const [faceModal, setFaceModal] = useState(null);
  const [form, setForm]           = useState({ name:"", role:"연구원" });

  const refresh = () => fetch("/api/researchers").then(r => r.json()).then(setList);
  useEffect(() => { refresh(); }, []);

  const openAdd  = () => { setForm({ name:"", role:"연구원" }); setModal({ mode:"add" }); };
  const openEdit = (r) => { setForm({ name:r.name, role:r.role }); setModal({ mode:"edit", data:r }); };

  const save = () => {
    if (!form.name.trim()) return alert("이름을 입력하세요");
    const url    = modal.mode==="add" ? "/api/researchers" : `/api/researchers/${modal.data.id}`;
    const method = modal.mode==="add" ? "POST" : "PUT";
    fetch(url, { method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(form) })
      .then(() => { refresh(); setModal(null); });
  };

  const del = (id, name) => {
    if (!confirm(`${name} 연구원을 삭제하시겠습니까?`)) return;
    fetch(`/api/researchers/${id}`, { method:"DELETE" }).then(() => refresh());
  };

  return (
    <div>
      {faceModal && (
        <FaceRegisterModal researcher={faceModal} onClose={() => { setFaceModal(null); refresh(); }} onDone={refresh}/>
      )}

      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
        <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          연구원 목록
          <Btn primary onClick={openAdd}>+ 연구원 등록</Btn>
        </div>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead>
            <tr>{["이름","권한","얼굴 등록","등록일","관리"].map(h =>
              <th key={h} style={{ textAlign:"left", padding:"8px 12px", borderBottom:`2px solid ${C.border}`, color:C.textDim, fontSize:11, fontWeight:600 }}>{h}</th>
            )}</tr>
          </thead>
          <tbody>{list.map((r, i) => (
            <tr key={r.id} style={{ background:i%2?C.surface2:C.surface }}>
              <td style={{ padding:"7px 12px", fontWeight:500 }}>{r.name}</td>
              <td style={{ padding:"7px 12px" }}><Badge type={r.role==="관리자"?"info":"ok"}>{r.role}</Badge></td>
              <td style={{ padding:"7px 12px" }}>
                {r.face_registered
                  ? <Btn small onClick={() => setFaceModal(r)}>🔄 재등록</Btn>
                  : <Btn small primary onClick={() => setFaceModal(r)}>📷 얼굴 등록</Btn>}
              </td>
              <td style={{ padding:"7px 12px", fontFamily:"Consolas", fontSize:11, color:C.textDim }}>{r.created}</td>
              <td style={{ padding:"7px 12px" }}>
                <Btn small onClick={() => openEdit(r)} style={{ marginRight:6 }}>수정</Btn>
                <Btn small danger onClick={() => del(r.id, r.name)}>삭제</Btn>
              </td>
            </tr>
          ))}</tbody>
        </table>
        {list.length===0 && <div style={{ textAlign:"center", padding:32, color:C.textDim }}>등록된 연구원이 없습니다.</div>}
      </div>

      {modal && (
        <div onClick={() => setModal(null)} style={{ position:"fixed", inset:0, background:"rgba(0,0,0,.4)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:999 }}>
          <div onClick={e => e.stopPropagation()} style={{ background:C.surface, borderRadius:8, boxShadow:"0 12px 40px rgba(0,0,0,.2)", width:420, overflow:"hidden" }}>
            <div style={{ padding:"14px 18px", borderBottom:`1px solid ${C.border}`, display:"flex", justifyContent:"space-between", alignItems:"center", fontSize:15, fontWeight:600 }}>
              {modal.mode==="add" ? "연구원 등록" : "연구원 수정"}
              <button onClick={() => setModal(null)} style={{ width:28, height:28, border:"none", background:"transparent", borderRadius:4, cursor:"pointer", fontSize:16, color:C.textDim }}>✕</button>
            </div>
            <div style={{ padding:18 }}>
              <div style={{ marginBottom:14 }}>
                <div style={{ fontSize:12, fontWeight:500, marginBottom:6 }}>이름</div>
                <input value={form.name} onChange={e => setForm(p => ({...p, name:e.target.value}))} placeholder="연구원 이름"
                  style={{ height:34, padding:"0 10px", border:`1px solid ${C.border2}`, borderRadius:6, fontSize:13, width:"100%" }}/>
              </div>
              <div style={{ marginBottom:20 }}>
                <div style={{ fontSize:12, fontWeight:500, marginBottom:6 }}>권한</div>
                <select value={form.role} onChange={e => setForm(p => ({...p, role:e.target.value}))}
                  style={{ height:34, padding:"0 10px", border:`1px solid ${C.border2}`, borderRadius:6, fontSize:13, width:"100%" }}>
                  <option value="관리자">관리자</option>
                  <option value="연구원">연구원</option>
                </select>
              </div>
              <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
                <Btn onClick={() => setModal(null)}>취소</Btn>
                <Btn primary onClick={save}>{modal.mode==="add"?"등록":"저장"}</Btn>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}