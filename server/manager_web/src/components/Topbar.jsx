import { C } from "../styles";
const META = {
  dashboard:   { t:"대시보드",    s:"운영 현황 요약" },
  researchers: { t:"연구원 관리", s:"등록 · 수정 · 삭제 · 얼굴 등록" },
  usage:       { t:"실험 이력",   s:"로봇 사용 기록 · 오류 이력" },
  settings:    { t:"시스템 설정", s:"장비 · 가스 · 온습도 설정" },
};
export default function Topbar({ tab }) {
  const m = META[tab];
  return (
    <div style={{ height:50, flexShrink:0, background:C.surface, borderBottom:`1px solid ${C.border}`, display:"flex", alignItems:"center", padding:"0 20px", gap:10 }}>
      <span style={{ fontSize:17, fontWeight:600 }}>{m.t}</span>
      <span style={{ fontSize:12, color:C.textDim }}>{m.s}</span>
    </div>
  );
}
