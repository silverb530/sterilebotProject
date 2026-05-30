#!/usr/bin/env python3
# =============================================================
#  SterileBot - 시험관 위치 추적 모듈
#  파일명: tube_state.py
#
#  ▶ 역할
#    - 각 시험관(tube_1 ~ tube_4)이 현재 어디에 있는지 추적
#    - 로봇 그리퍼 상태(open/closed, 잡고 있는 tube) 추적
#    - 변경 사항을 tube_state.json 에 영구 저장
#    - RESET 시 원위치 복귀 계획 자동 생성
#
#  ▶ 위치 표현
#    bottle_1 ~ bottle_4 : 시약통 (원래 자리)
#    A1 ~ A4             : A_tubes 슬롯
#    B1 ~ B4             : B_tubes 슬롯
#    HELD                : 현재 그리퍼가 잡고 있음
#
#  ▶ 로봇 동작과의 매핑 (Zone_tracker가 호출)
#    pickup_move(N)  → mark_approach("pickup", "bottle_N")
#    drop_tube("A2") → mark_approach("drop",   "A2")
#    GRAB 제스처     → mark_grab()      # 그리퍼 닫힘, tube 잡음
#    RELEASE 제스처  → mark_release()   # 그리퍼 열림, tube 놓음
# =============================================================

import json
import os
import threading
from copy import deepcopy

STATE_FILE = "tube_state.json"

# 시약통 4개 = tube 4개 (1:1 대응이 디폴트)
DEFAULT_TUBES = {
    "tube_1": {"origin": "bottle_1", "location": "bottle_1"},
    "tube_2": {"origin": "bottle_2", "location": "bottle_2"},
    "tube_3": {"origin": "bottle_3", "location": "bottle_3"},
    "tube_4": {"origin": "bottle_4", "location": "bottle_4"},
}

DEFAULT_ROBOT = {
    "gripper":          "open",   # "open" | "closed"
    "holding":          None,     # None | "tube_1" ...
    "approach_kind":    None,     # None | "pickup" | "drop"
    "approach_target":  None,     # None | "bottle_1" | "A2" | ...
}


def short_loc(loc):
    """
    내부 위치 식별자를 화면 표시용 짧은 이름으로 변환.
      bottle_1 ~ bottle_4 → r1 ~ r4    (Reagent_bottles)
      A1 ~ A4             → a1 ~ a4    (A_tubes 슬롯)
      B1 ~ B4             → b1 ~ b4    (B_tubes 슬롯)
      HELD                → HLD
      기타                → 그대로
    """
    if loc is None:
        return "-"
    if loc.startswith("bottle_"):
        return "r" + loc[len("bottle_"):]
    if loc == "HELD":
        return "HLD"
    if len(loc) >= 2 and loc[0] in ("A", "B") and loc[1:].isdigit():
        return loc.lower()
    return loc


class TubeStateManager:
    """시험관 + 로봇 상태를 추적하고 JSON 파일에 영구 저장"""

    # ─────────────────────────────────────────
    #  init / persistence
    # ─────────────────────────────────────────
    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self._lock = threading.RLock()
        self.state = self._default_state()
        self.load()

    def _default_state(self):
        return {
            "tubes": deepcopy(DEFAULT_TUBES),
            "robot": deepcopy(DEFAULT_ROBOT),
        }

    def load(self):
        """파일에서 불러오기. 실패하면 기본값 유지."""
        with self._lock:
            if not os.path.exists(self.state_file):
                print(f"[STATE] 새 상태 파일 생성 예정: {self.state_file}")
                self.save()
                return True
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.state = self._merge_with_default(loaded)
                print(f"[STATE] 로드 완료: {self.state_file}")
                self._print_summary()
                return True
            except Exception as e:
                print(f"[STATE] 로드 실패 ({e}) → 기본값 사용")
                self.state = self._default_state()
                return False

    def _merge_with_default(self, loaded):
        """저장 파일이 일부만 있어도 기본 구조에 안전하게 병합"""
        merged = self._default_state()
        if isinstance(loaded.get("tubes"), dict):
            for tid, info in loaded["tubes"].items():
                if tid in merged["tubes"] and isinstance(info, dict):
                    merged["tubes"][tid].update({
                        k: v for k, v in info.items()
                        if k in ("origin", "location")
                    })
        if isinstance(loaded.get("robot"), dict):
            for k, v in loaded["robot"].items():
                if k in merged["robot"]:
                    merged["robot"][k] = v
        return merged

    def save(self):
        with self._lock:
            try:
                tmp = self.state_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.state_file)
                return True
            except Exception as e:
                print(f"[STATE] 저장 실패: {e}")
                return False

    def _print_summary(self):
        for tid, info in self.state["tubes"].items():
            mark = "✓" if info["location"] == info["origin"] else "→"
            print(f"  {mark} {tid}: {info['location']}"
                  f"  (origin={info['origin']})")
        r = self.state["robot"]
        print(f"  [robot] gripper={r['gripper']}  holding={r['holding']}"
              f"  approach={r['approach_kind']}/{r['approach_target']}")

    # ─────────────────────────────────────────
    #  조회
    # ─────────────────────────────────────────
    def snapshot(self):
        with self._lock:
            return deepcopy(self.state)

    def get_tube(self, tube_id):
        with self._lock:
            return deepcopy(self.state["tubes"].get(tube_id))

    def get_robot(self):
        with self._lock:
            return deepcopy(self.state["robot"])

    def get_tube_at(self, location):
        """해당 위치에 있는 tube_id 반환 (없으면 None)"""
        with self._lock:
            for tid, info in self.state["tubes"].items():
                if info["location"] == location:
                    return tid
            return None

    def get_moved_tubes(self):
        """원래 자리를 벗어난 tube 목록 [(tid, location, origin), ...]"""
        with self._lock:
            return [
                (tid, info["location"], info["origin"])
                for tid, info in self.state["tubes"].items()
                if info["location"] != info["origin"]
            ]

    def all_at_origin(self):
        with self._lock:
            return all(
                info["location"] == info["origin"]
                for info in self.state["tubes"].values()
            )

    def is_holding(self):
        with self._lock:
            return self.state["robot"]["holding"] is not None

    def short_status_line(self):
        """UI 한 줄용: 'T1:r1  T2:a2  T3:HLD  T4:b1'"""
        with self._lock:
            parts = []
            for tid in sorted(self.state["tubes"].keys()):
                loc   = self.state["tubes"][tid]["location"]
                short = short_loc(loc)
                num   = tid.split("_")[1]
                parts.append(f"T{num}:{short}")
            return "  ".join(parts)

    # ─────────────────────────────────────────
    #  이벤트 (로봇 동작 시점마다 호출)
    # ─────────────────────────────────────────
    def mark_approach(self, kind, target):
        """
        pickup_move / drop_tube 호출 직후 호출.
        아직 잡거나 놓지 않은, '도달만 한' 상태를 기록.
          kind  : "pickup" | "drop"
          target: "bottle_1" | "A2" | "B3" ...
        """
        with self._lock:
            self.state["robot"]["approach_kind"]   = kind
            self.state["robot"]["approach_target"] = target
            print(f"[STATE] approach: {kind} → {target}")
        self.save()

    def mark_grab(self):
        """
        GRAB 제스처 → 그리퍼 닫고 approach_target 위치의 tube를 잡음.
        approach_kind 와 무관하게 target 위치에 tube 가 있으면 잡음
        (시약통에서 잡든, 슬롯에서 다시 꺼내든 동일하게 처리).
        성공: 잡힌 tube_id 반환 / 실패: None
        """
        with self._lock:
            r = self.state["robot"]

            # 이미 잡고 있으면 무시
            if r["holding"] is not None:
                print(f"[STATE] 이미 {r['holding']} 잡고 있음 — grab 무시")
                return r["holding"]

            target = r["approach_target"]
            if target is None:
                r["gripper"] = "closed"
                print("[STATE] approach_target 없음 — 그리퍼만 닫힘")
                self.save()
                return None

            # target 위치에 있는 tube 찾기 (kind 무관)
            tid = None
            for t, info in self.state["tubes"].items():
                if info["location"] == target:
                    tid = t
                    break

            if tid is None:
                r["gripper"] = "closed"
                print(f"[STATE] {target} 에 잡을 tube 없음 — 그리퍼만 닫힘")
                self.save()
                return None

            # tube 잡음
            self.state["tubes"][tid]["location"] = "HELD"
            r["gripper"] = "closed"
            r["holding"] = tid
            print(f"[STATE] GRAB: {tid} (← {target})")

        self.save()
        return tid

    def mark_release(self):
        """
        RELEASE 제스처 → 그리퍼 열고 잡은 tube를 approach_target 위치에 놓음.
        성공: 놓인 tube_id 반환 / 실패: None
        """
        with self._lock:
            r = self.state["robot"]
            tid = r["holding"]

            if tid is None:
                # 잡고 있는 게 없으면 그리퍼만 열기
                r["gripper"] = "open"
                print("[STATE] 잡은 것 없음 — 그리퍼만 열림")
                self.save()
                return None

            # 어디에 놓을지 결정:
            # - approach가 "drop"이고 target이 있으면 그곳에 놓기
            # - 아니면 현재 approach_target (예: pickup 후 같은 자리에 놓기)
            # - 둘 다 없으면 원래 자리(origin)로 복귀
            target = r["approach_target"]
            if target is None:
                target = self.state["tubes"][tid]["origin"]
                print(f"[STATE] approach_target 없음 → origin({target})에 놓음")

            self.state["tubes"][tid]["location"] = target
            r["gripper"]         = "open"
            r["holding"]         = None
            r["approach_kind"]   = None
            r["approach_target"] = None
            print(f"[STATE] RELEASE: {tid} → {target}")

        self.save()
        return tid

    def force_clear_approach(self):
        """STAGE1으로 돌아갈 때 등 — 잡지도 놓지도 않은 approach 정보만 비우기"""
        with self._lock:
            self.state["robot"]["approach_kind"]   = None
            self.state["robot"]["approach_target"] = None
        self.save()

    # ─────────────────────────────────────────
    #  RESET
    # ─────────────────────────────────────────
    def reset_to_default(self):
        """완전 초기화 — 모든 시험관이 원래 자리, 그리퍼 열림"""
        with self._lock:
            self.state = self._default_state()
        self.save()
        print("[STATE] 완전 초기화 완료")

    def reset_robot_only(self):
        """시험관 위치는 유지, 그리퍼/approach 상태만 초기화"""
        with self._lock:
            self.state["robot"] = deepcopy(DEFAULT_ROBOT)
        self.save()
        print("[STATE] 로봇 상태만 초기화")

    def build_reset_plan(self):
        """
        현재 상태에서 모든 시험관을 원래 자리로 되돌리는 실행 계획.
        반환 형식:
          [
            {"step": 1, "tube": "tube_2", "action": "release_at_origin"},
            {"step": 2, "tube": "tube_3", "from": "A1", "to": "bottle_3",
             "action": "return_from_slot"},
            ...
          ]
        action 종류:
          - "release_at_origin": 잡고 있는 tube를 원래 자리에 놓기만
          - "return_from_slot" : 슬롯에서 집어서 원래 자리로 되돌리기
        """
        plan = []
        with self._lock:
            step = 1

            # 1) 잡고 있는 tube 먼저 처리 — 어디로 가던 중이든 원래 자리로
            holding = self.state["robot"]["holding"]
            if holding is not None:
                origin = self.state["tubes"][holding]["origin"]
                plan.append({
                    "step": step,
                    "tube": holding,
                    "from": "HELD",
                    "to":   origin,
                    "action": "release_at_origin",
                })
                step += 1

            # 2) 슬롯에 옮겨진 tube들을 번호 순서로 (tube_1 → tube_2 → ...)
            for tid in sorted(self.state["tubes"].keys()):
                info = self.state["tubes"][tid]
                if tid == holding:
                    continue  # 이미 위에서 처리됨
                loc    = info["location"]
                origin = info["origin"]
                if loc == "HELD":
                    continue  # 잡고 있는 게 따로 있을 리는 없지만 안전망
                if loc != origin:
                    plan.append({
                        "step": step,
                        "tube": tid,
                        "from": loc,
                        "to":   origin,
                        "action": "return_from_slot",
                    })
                    step += 1
        return plan


# ─────────────────────────────────────────────
#  단독 실행: 현재 상태 확인용
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mgr = TubeStateManager()
    print("\n[현재 스냅샷]")
    print(json.dumps(mgr.snapshot(), indent=2, ensure_ascii=False))
    print("\n[옮겨진 시험관]")
    for tid, loc, origin in mgr.get_moved_tubes():
        print(f"  {tid}: {loc}  (원래 {origin})")
    print("\n[RESET 계획]")
    for p in mgr.build_reset_plan():
        print(f"  step{p['step']}: {p['action']} — {p['tube']} "
              f"{p.get('from','')} → {p['to']}")
    if "--clear" in sys.argv:
        if input("\n정말 초기화? (y/n): ").strip().lower() == "y":
            mgr.reset_to_default()
            print("초기화 완료")