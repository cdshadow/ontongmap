# -*- coding: utf-8 -*-
"""
ontongmap 일일 갱신 + GitHub 푸시

    python update_and_push.py

동작:
    1. place_map_api(perfect)_v8_cl.py 실행 -> index.html 갱신
    2. index.html 이 바뀐 경우에만 커밋
    3. origin main 에 푸시 (--force-with-lease)

종료 코드:
    0  성공 (또는 변경 없음)
    1  실패
"""

import os
import subprocess
import sys
from datetime import datetime

# ── 설정 ────────────────────────────────────────────────────────────
REPO = r"D:\d\01_code\py\ontongmap"
SCRIPT = "place_map_api(perfect)_v8_cl.py"
TARGET = "index.html"
BRANCH = "main"
SCRIPT_TIMEOUT = 1800        # 지도 생성 최대 30분

YMD = datetime.now().strftime("%Y%m%d")
LOG_DIR = os.path.join(REPO, "_log")
LOG_PATH = os.path.join(LOG_DIR, f"push_{YMD[:6]}.log")


def say(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, timeout=120):
    """명령 실행. (returncode, 출력) 반환. 출력은 로그에도 남긴다."""
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=timeout)
    out = (p.stdout + p.stderr).decode("utf-8", "replace").strip()
    if out:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(out + "\n")
    return p.returncode, out


def fail(*lines):
    for ln in lines:
        say(ln)
    sys.exit(1)


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    say("=" * 58)
    say(f"시작  {YMD}")

    if not os.path.isdir(REPO):
        fail(f"[실패] 저장소 폴더 없음: {REPO}")

    # ── 1. 지도 생성 ──
    say(f"[1/4] {SCRIPT} 실행")
    script_path = os.path.join(REPO, SCRIPT)
    if not os.path.exists(script_path):
        fail(f"[실패] 스크립트 없음: {script_path}")

    try:
        # sys.executable = 지금 이 스크립트를 돌리는 파이썬.
        # conda 환경이든 뭐든 동일한 인터프리터가 보장된다.
        rc, out = run([sys.executable, script_path], timeout=SCRIPT_TIMEOUT)
    except subprocess.TimeoutExpired:
        fail(f"[실패] 스크립트가 {SCRIPT_TIMEOUT}초 내에 끝나지 않음")

    if rc != 0:
        fail(f"[실패] 스크립트가 오류로 종료됨 (exit {rc})",
             "       위 로그의 파이썬 트레이스백을 확인할 것")

    target_path = os.path.join(REPO, TARGET)
    if not os.path.exists(target_path):
        fail(f"[실패] {TARGET} 이 생성되지 않음")

    age = (datetime.now() -
           datetime.fromtimestamp(os.path.getmtime(target_path)))
    say(f"      {TARGET} 확인됨 (수정 {int(age.total_seconds() // 60)}분 전)")

    # ── 2. 변경 확인 (index.html 만) ──
    say(f"[2/4] {TARGET} 변경 여부 확인")
    rc, out = run(["git", "status", "--porcelain", "--", TARGET])
    if rc != 0:
        fail("[실패] git status 실패. 이 폴더가 git 저장소가 맞는지 확인할 것")
    if not out:
        say(f"      {TARGET} 변경 없음. 커밋/푸시를 건너뜀.")
        say("      주의: 매일 동일하다면 스크립트가 실제로 갱신하는지 확인 필요")
        sys.exit(0)
    say(f"      변경 감지: {out}")

    # ── 3. 커밋 (index.html 만) ──
    say("[3/4] 커밋")
    rc, _ = run(["git", "add", "--", TARGET])
    if rc != 0:
        fail("[실패] git add 실패")

    rc, out = run(["git", "commit", "-m", f"update ontongmap_{YMD}",
                   "--", TARGET])
    if rc != 0:
        fail("[실패] 커밋 실패.",
             "       git config user.name / user.email 설정을 확인할 것")

    # ── 4. 푸시 ──
    # --force-with-lease: 내가 마지막으로 본 원격 상태와 다르면 거부한다.
    # 평소엔 --force와 동일, 남의 커밋을 지울 상황에서만 멈춘다.
    say("[4/4] 푸시")
    rc, out = run(["git", "push", "-u", "origin", BRANCH,
                   "--force-with-lease"], timeout=300)
    if rc != 0:
        msg = ["[실패] 푸시 실패."]
        low = out.lower()
        if "stale info" in low or "rejected" in low:
            msg.append("       원격에 내가 모르는 커밋이 있습니다.")
            msg.append("       git fetch 후 내용을 직접 확인하고 수동 처리할 것.")
        elif "authentication" in low or "credential" in low or "403" in low:
            msg.append("       인증 실패. git config --get credential.helper 확인.")
        fail(*msg)

    say(f"[완료] {YMD} 푸시 성공")


if __name__ == "__main__":
    main()
