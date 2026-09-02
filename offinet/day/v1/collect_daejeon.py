# -*- coding: utf-8 -*-
"""
대전 5개 구 주유소 가격 일일 수집기

    python collect_daejeon.py                  # 오늘 날짜
    python collect_daejeon.py --date 20260902  # 날짜 지정
    python collect_daejeon.py --force          # 이미 받은 날도 다시 받기

동작:
    1. BASE\\YYYYMMDD\\raw\\ 에 구별 .xls 5개 다운로드
    2. 병합/정제해서 BASE\\YYYYMMDD\\대전주유소_YYYYMMDD.csv
    3. BASE\\_누적\\대전주유소_누적.csv 에 반영
    4. 검증 실패 시 exit code 1 (예약 작업이 실패를 인지할 수 있게)

필요 패키지:
    pip install pandas xlrd requests
"""

import argparse
import json
import logging
import os
import sys
import time
from urllib.parse import quote
from datetime import datetime

import pandas as pd
import requests

# ── 설정 ────────────────────────────────────────────────────────────
BASE = r"D:\d\01_code\py\ontongmap\offinet\day"
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "request.json")

GU_LIST = ["동구", "중구", "서구", "유성구", "대덕구"]

COLS = ["지역", "상호", "주소", "상표", "전화번호", "셀프여부",
        "고급휘발유", "휘발유", "경유", "실내등유"]
PRICE_COLS = ["고급휘발유", "휘발유", "경유", "실내등유"]

MIN_ROWS_PER_GU = 5      # 이보다 적으면 수집 실패로 간주
RETRIES = 3
RETRY_WAIT = 20          # 초

log = logging.getLogger("opinet")


def setup_log(ymd):
    d = os.path.join(BASE, "_log")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"collect_{ymd[:6]}.log")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s")
    for h in (logging.FileHandler(path, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        log.addHandler(h)


# ── 1. 다운로드 ─────────────────────────────────────────────────────
def load_config():
    """request.json: 브라우저에서 뜬 다운로드 요청을 그대로 옮겨둔 파일."""
    if not os.path.exists(CONFIG):
        log.error("request.json 이 없습니다. 아직 요청 정보가 설정되지 않았습니다.")
        log.error("경로: %s", CONFIG)
        sys.exit(2)
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def make_session(cfg):
    """세션 워밍업: 검색 페이지를 먼저 열어 쿠키를 새로 발급받는다.
    쿠키를 설정에 박아두면 만료 시 조용히 실패하므로 매 실행마다 새로 받는다."""
    s = requests.Session()
    s.headers.update(cfg["request"].get("headers", {}))
    url = cfg.get("warmup_url")
    if url:
        try:
            s.get(url, timeout=30)
            names = ", ".join(sorted(c.name for c in s.cookies))
            log.info("세션 준비 완료 (쿠키: %s)", names or "없음")
        except Exception as e:
            log.warning("세션 워밍업 실패, 쿠키 없이 진행: %s", e)
    return s


def fetch_gu(sess, cfg, gu, dest):
    """구 하나의 xls를 내려받아 dest에 저장. 실패 시 예외."""
    spec = cfg["request"]
    code = cfg["gu_codes"][gu]
    if code == "TODO":
        raise ValueError(f"{gu}의 SIGUN_CD가 request.json에 설정되지 않았습니다")

    # POLL_DIV_CD 처럼 같은 키가 반복되므로 body를 문자열 그대로 다룬다
    body = (spec["body"]
            .replace("{GU_CODE}", code)
            .replace("{GU_NM}", quote(gu)))

    r = sess.post(spec["url"], data=body.encode("utf-8"), timeout=60)
    r.raise_for_status()

    # HTML(에러/대기열/세션만료 페이지)이 돌아오는 경우를 걸러낸다
    head = r.content[:8]
    if not (head.startswith(b"\xd0\xcf\x11\xe0") or head.startswith(b"PK")):
        snippet = r.content[:200].decode("utf-8", "replace").replace("\n", " ")
        raise ValueError(f"엑셀이 아닌 응답 ({len(r.content)} bytes): {snippet}")

    with open(dest, "wb") as f:
        f.write(r.content)
    return len(r.content)


def download_all(cfg, raw_dir, force):
    todo = [g for g in GU_LIST
            if force or not os.path.exists(os.path.join(raw_dir, f"{g}.xls"))]
    if not todo:
        log.info("5개 구 모두 이미 받아져 있음")
        return GU_LIST[:], []

    sess = make_session(cfg)
    ok, failed = [g for g in GU_LIST if g not in todo], []

    for gu in todo:
        dest = os.path.join(raw_dir, f"{gu}.xls")
        for attempt in range(1, RETRIES + 1):
            try:
                n = fetch_gu(sess, cfg, gu, dest)
                log.info("%s: 다운로드 완료 (%d bytes)", gu, n)
                ok.append(gu)
                break
            except Exception as e:
                log.warning("%s: %d/%d회 실패 - %s", gu, attempt, RETRIES, e)
                if attempt < RETRIES:
                    time.sleep(RETRY_WAIT)
                    sess = make_session(cfg)   # 세션 문제일 수 있으니 재발급
                else:
                    failed.append(gu)
        time.sleep(3)   # 서버 부담 줄이기
    return ok, failed


# ── 2. 병합/정제 ────────────────────────────────────────────────────
def read_one(path):
    df = pd.read_excel(path, engine="xlrd", header=2)
    df = df.rename(columns=lambda c: str(c).strip())
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError(f"컬럼 없음 {missing} (실제: {list(df.columns)})")
    return df[COLS].dropna(subset=["상호"]).copy()


def build(raw_dir, ymd):
    frames, counts = [], {}
    for gu in GU_LIST:
        p = os.path.join(raw_dir, f"{gu}.xls")
        if not os.path.exists(p):
            continue
        try:
            d = read_one(p)
            counts[gu] = len(d)
            frames.append(d)
        except Exception as e:
            log.error("%s.xls 파싱 실패: %s", gu, e)

    if not frames:
        return None, counts

    df = pd.concat(frames, ignore_index=True)

    for c in PRICE_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["지역", "상호", "주소", "상표", "전화번호", "셀프여부"]:
        df[c] = df[c].astype(str).str.strip()

    df["구"] = df["주소"].str.extract(r"대전(?:광역시)?\s+(\S+구)")
    df["셀프여부"] = df["셀프여부"].map({"Y": True, "N": False}).astype("boolean")
    df.insert(0, "조사일자", ymd)

    order = (["조사일자", "지역", "구", "상호", "주소", "상표",
              "전화번호", "셀프여부"] + PRICE_COLS)
    df = df[order].drop_duplicates(subset=["조사일자", "상호", "주소"])
    return df.sort_values(["구", "휘발유"], na_position="last").reset_index(drop=True), counts


def update_cumulative(df, ymd):
    d = os.path.join(BASE, "_누적")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "대전주유소_누적.csv")
    if os.path.exists(path):
        old = pd.read_csv(path, dtype={"조사일자": str})
        old = old[old["조사일자"] != ymd]          # 같은 날짜는 교체
        allx = pd.concat([old, df], ignore_index=True)
    else:
        allx = df
    allx.to_csv(path, index=False, encoding="utf-8-sig")
    return path, len(allx), allx["조사일자"].nunique()


# ── 3. 실행 ─────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--base", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    global BASE
    if args.base:
        BASE = args.base

    # 실행 시각에서 날짜를 찍는다. 보충 실행으로 늦게 돌아도
    # '실행된 날'로 기록되므로 조사일자와 실제 수집일이 어긋나지 않는다.
    ymd = args.date or datetime.now().strftime("%Y%m%d")

    setup_log(ymd)
    log.info("=" * 55)
    log.info("수집 시작  조사일자=%s", ymd)

    day_dir = os.path.join(BASE, ymd)
    raw_dir = os.path.join(day_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    cfg = load_config()
    ok, failed = download_all(cfg, raw_dir, args.force)

    df, counts = build(raw_dir, ymd)
    if df is None:
        log.error("병합 실패: 읽을 수 있는 파일이 없습니다.")
        sys.exit(1)

    out = os.path.join(day_dir, f"대전주유소_{ymd}.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    log.info("저장: %s (%d개소)", out, len(df))

    path, rows, days = update_cumulative(df, ymd)
    log.info("누적: %s (%d행 / %d일치)", path, rows, days)

    # ── 검증 ──
    problems = []
    if failed:
        problems.append(f"다운로드 실패: {failed}")

    # 5개 구가 실제로 다른 파일인지 확인 (SIGUN_CD 없이 이름으로만 거는 방식 검증)
    import hashlib
    hashes = {}
    for gu in GU_LIST:
        p = os.path.join(raw_dir, f"{gu}.xls")
        if os.path.exists(p):
            hashes[gu] = hashlib.md5(open(p, "rb").read()).hexdigest()[:8]
    dup = [g for g in hashes if list(hashes.values()).count(hashes[g]) > 1]
    if dup:
        problems.append(
            f"동일한 파일이 중복 수신됨: {sorted(dup)} — "
            f"구 이름만으로는 필터가 안 되는 것으로 보입니다. "
            f"각 구의 SIGUN_CD를 request.json에 채워야 합니다.")

    thin = [g for g, n in counts.items() if n < MIN_ROWS_PER_GU]
    if thin:
        problems.append(f"데이터가 비정상적으로 적음: {thin}")
    got = set(df["구"].dropna())
    if set(GU_LIST) - got:
        problems.append(f"누락된 구: {sorted(set(GU_LIST) - got)}")

    log.info("구별: %s", {g: counts.get(g, 0) for g in GU_LIST})

    if problems:
        for p in problems:
            log.error(p)
        sys.exit(1)

    log.info("정상 완료: 총 %d개소", len(df))


if __name__ == "__main__":
    main()
