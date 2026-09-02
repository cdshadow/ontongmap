"""오피넷 '지역_위치별(주유소).xls'를 상호·주소·휘발유 3개 열의 CSV로 변환한다.

입력  : 지역_위치별(주유소).xls  (BIFF 형식의 구형 .xls, xlrd로 읽음)
출력  : 지역_위치별(주유소)_cl.csv  (utf-8-sig, Excel에서 한글이 깨지지 않음)

- 원본 .xls는 1~2행이 제목·단위 표기이고 3행이 헤더이므로, 행 번호를 고정하지 않고
  '상호'와 '주소'가 함께 들어 있는 행을 찾아 헤더로 사용한다.
- 열 위치도 고정하지 않고 헤더 이름으로 찾으므로 원본의 열 순서가 바뀌어도 동작한다.
- 원본의 행 순서를 그대로 유지한다(별도 정렬 없음).

실행 방법:
    python 주유소_xls_to_csv_cl.py
    python 주유소_xls_to_csv_cl.py "다른입력.xls" "다른출력.csv"
"""

from pathlib import Path
import csv
import sys

import xlrd

# --- 설정값 -----------------------------------------------------------------
BASE_DIR = Path(__file__).parent

INPUT_NAME = "지역_위치별(주유소).xls"
OUTPUT_NAME = "지역_위치별(주유소)_cl.csv"

# 헤더를 찾을 때 반드시 함께 있어야 하는 열 이름
HEADER_KEYS = ("상호", "주소")

# 출력할 열과 순서 (원본 헤더 이름 기준)
OUT_COLUMNS = ["상호", "주소", "휘발유"]

# 값이 없음을 뜻하는 표기 (원본에서 '-'로 채워져 있음)
EMPTY_MARKS = {"", "-", "–", "—"}

CSV_ENCODING = "utf-8-sig"  # Excel에서 한글이 깨지지 않도록 BOM 포함
# ---------------------------------------------------------------------------


def cell_to_text(cell):
    """xlrd 셀 값을 CSV에 넣을 문자열로 바꾼다."""
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        value = cell.value
        # 1807.0 처럼 소수부가 없는 값은 정수로 표기한다.
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return ""
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return "Y" if cell.value else "N"
    return str(cell.value).strip()


def find_header_row(sheet):
    """'상호'와 '주소'가 모두 들어 있는 첫 행을 헤더로 판단한다."""
    for row_idx in range(sheet.nrows):
        texts = [cell_to_text(c) for c in sheet.row(row_idx)]
        if all(key in texts for key in HEADER_KEYS):
            return row_idx, texts
    raise RuntimeError(
        f"헤더 행을 찾지 못했습니다. {HEADER_KEYS} 열이 모두 있는 행이 없습니다."
    )


def resolve_output_path(path: Path) -> Path:
    """같은 이름의 파일이 있으면 덮어쓰지 않고 _v2, _v3 순으로 번호를 올린다."""
    if not path.exists():
        return path

    stem, suffix = path.stem, path.suffix
    base = stem[:-3] if stem.endswith("_cl") else stem
    tail = "_cl" if stem.endswith("_cl") else ""

    version = 2
    while True:
        candidate = path.with_name(f"{base}_v{version}{tail}{suffix}")
        if not candidate.exists():
            return candidate
        version += 1


def convert(input_path: Path, output_path: Path) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {input_path}")

    book = xlrd.open_workbook(str(input_path))
    sheet = book.sheet_by_index(0)
    print(f"[1] 원본 열기 완료: {input_path.name} (시트 '{sheet.name}', {sheet.nrows}행 {sheet.ncols}열)")

    header_row, header = find_header_row(sheet)
    print(f"[2] 헤더 행: {header_row + 1}행 -> {header}")

    missing = [name for name in OUT_COLUMNS if name not in header]
    if missing:
        raise RuntimeError(f"원본에 없는 열이 있습니다: {missing}")
    col_index = {name: header.index(name) for name in OUT_COLUMNS}

    rows = []
    for row_idx in range(header_row + 1, sheet.nrows):
        values = [cell_to_text(sheet.cell(row_idx, col_index[name])) for name in OUT_COLUMNS]
        # 상호와 주소가 모두 비어 있으면 데이터 행이 아니므로 건너뛴다.
        if all(v in EMPTY_MARKS for v in values[:2]):
            continue
        rows.append(values)
    print(f"[3] 데이터 행 추출: {len(rows)}건")

    output_path = resolve_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding=CSV_ENCODING, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(OUT_COLUMNS)
        writer.writerows(rows)
    print(f"[4] CSV 저장 완료: {output_path.resolve()}")

    return output_path


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / INPUT_NAME
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / OUTPUT_NAME

    if not input_path.is_absolute():
        input_path = BASE_DIR / input_path
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path

    saved = convert(input_path, output_path)
    print(f"\n저장 경로: {saved.resolve()}")


if __name__ == "__main__":
    main()
