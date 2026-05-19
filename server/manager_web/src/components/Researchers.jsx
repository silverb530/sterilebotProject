import { useState, useEffect } from "react";
import { C } from "../styles";

function Badge({ type, children }) {
  const colors = { ok:{bg:C.greenDim,c:C.green}, warn:{bg:C.amberDim,c:C.amber}, err:{bg:C.redDim,c:C.red}, info:{bg:C.accentDim,c:C.accent} };
  const cl = colors[type] || colors.info;
  return <span style={{ display:"inline-flex", padding:"2px 10px", borderRadius:20, fontSize:11, fontWeight:500, background:cl.bg, color:cl.c }}>{children}</span>;
}
function Btn({ children, primary, danger, small, onClick, style={} }) {
  return <button onClick={onClick} style={{ height:small?26:32, padding:small?"0 10px":"0 14px", background:primary?C.accent:danger?C.redDim:C.surface, border:`1px solid ${primary?C.accent:danger?C.red:C.border2}`, borderRadius:6, fontSize:small?11:12, color:primary?"#fff":danger?C.red:C.textMid, fontWeight:primary?500:400, cursor:"pointer", display:"inline-flex", alignItems:"center", gap:6, ...style }}>{children}</button>;
}

export default function Researchers() {
  const [list, setList] = useState([]);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({ name:"", role:"연구원" });

  const refresh = () => fetch("/api/researchers").then(r => r.json()).then(setList);
  useEffect(() => { refresh(); }, []);

  const openAdd = () => { setForm({ name:"", role:"연구원" }); setModal({ mode:"add" }); };
  const openEdit = (r) => { setForm({ name:r.name, role:r.role }); setModal({ mode:"edit", data:r }); };

  const save = () => {
    if (!form.name.trim()) return alert("이름을 입력하세요");
    const url = modal.mode==="add" ? "/api/researchers" : `/api/researchers/${modal.data.id}`;
    const method = modal.mode==="add" ? "POST" : "PUT";
    fetch(url, { method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(form) })
      .then(() => { refresh(); setModal(null); });
  };

  const del = (id, name) => {
    if (!confirm(`${name} 연구원을 삭제하시겠습니까?`)) return;
    fetch(`/api/researchers/${id}`, { method:"DELETE" }).then(() => refresh());
  };

  const regFace = (id) => {
    fetch(`/api/researchers/${id}/face`, { method:"POST" }).then(() => { refresh(); alert("얼굴 등록 완료!"); });
  };

  return (
    <div>
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:6, boxShadow:"0 1px 3px rgba(0,0,0,.05)" }}>
        <div style={{ padding:"12px 16px", borderBottom:`1px solid ${C.border}`, fontSize:14, fontWeight:600, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          연구원 목록
          <Btn primary onClick={openAdd}>+ 연구원 등록</Btn>
        </div>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead><tr>{["이름","권한","얼굴 등록","등록일","관리"].map(h=><th key={h} style={{ textAlign:"left", padding:"8px 12px", borderBottom:`2px solid ${C.border}`, color:C.textDim, fontSize:11, fontWeight:600 }}>{h}</th>)}</tr></thead>
          <tbody>{list.map((r,i) => (
            <tr key={r.id} style={{ background:i%2?C.surface2:C.surface }}>
              <td style={{ padding:"7px 12px", fontWeight:500 }}>{r.name}</td>
              <td style={{ padding:"7px 12px" }}><Badge type={r.role==="관리자"?"info":"ok"}>{r.role}</Badge></td>
              <td style={{ padding:"7px 12px" }}>{r.face_registered ? <Badge type="ok">등록됨</Badge> : <Btn small primary onClick={() => regFace(r.id)}>📷 얼굴 등록</Btn>}</td>
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
              <div style={{ marginBottom:14 }}><div style={{ fontSize:12, fontWeight:500, marginBottom:6 }}>이름</div><input value={form.name} onChange={e => setForm(p => ({...p, name:e.target.value}))} placeholder="연구원 이름" style={{ height:34, padding:"0 10px", border:`1px solid ${C.border2}`, borderRadius:6, fontSize:13, width:"100%" }}/></div>
              <div style={{ marginBottom:20 }}><div style={{ fontSize:12, fontWeight:500, marginBottom:6 }}>권한</div><select value={form.role} onChange={e => setForm(p => ({...p, role:e.target.value}))} style={{ height:34, padding:"0 10px", border:`1px solid ${C.border2}`, borderRadius:6, fontSize:13, width:"100%" }}><option value="관리자">관리자</option><option value="연구원">연구원</option></select></div>
              <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}><Btn onClick={() => setModal(null)}>취소</Btn><Btn primary onClick={save}>{modal.mode==="add"?"등록":"저장"}</Btn></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
