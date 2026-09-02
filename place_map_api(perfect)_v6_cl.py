# place_map_api_v6(온통대전 가맹점 + 오늘 날짜 주유소 휘발유 가격)
#
# 두 개의 CSV를 함께 읽어 하나의 index.html을 만든다.
#
#   place_map_template.csv                              온통대전 가맹점 -> 파란색 마커
#   offinet/day/{오늘날짜}/대전주유소_{오늘날짜}.csv     주유소          -> 빨간색 마커
#
# 주유소 자료는 매일 새벽 2시에 그날 날짜의 폴더가 만들어지고 그 안에 쌓이므로,
# 실행하는 날의 날짜로 폴더와 파일 이름을 만들어 불러온다.
#
# 온통대전 가맹점은 주유소와 같은 열기구(핀) 모양이되
# 테두리만 파란색으로 그리고 속은 비워 둔다.
# 주유소는 빨간색 핀 마커로 그린다. 두 마커 모두 반투명하지 않은 진한 색이다.
# 주유소 마커에는 휘발유 가격을 항상 보이는 라벨로 붙인다.
# 화면 우측 상단의 "현위치" 버튼은 이전 버전과 동일하다.

import os
import requests
import pandas as pd
import folium

from datetime import date
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# 1. 현재 .py 파일이 있는 폴더 경로 가져오기
# ============================================================

base_dir = Path(__file__).parent


# ============================================================
# 2. .env 파일에서 Kakao API Key 불러오기
# ============================================================

env_path = base_dir / ".env"

load_dotenv(env_path)

api_key = os.getenv("KAKAO_API_KEY")

# API Key가 정상적으로 불러와졌는지 확인
if not api_key:
    raise ValueError(
        "KAKAO_API_KEY를 불러오지 못했습니다.\n"
        ".env 파일의 위치와 내용을 확인하세요."
    )


# ============================================================
# 3. Kakao API를 사용하여 주소 → 좌표 변환
# ============================================================

# 같은 주소를 여러 번 요청하지 않도록 결과를 담아 둔다.
coordinate_cache = {}


def get_coordinates(address, api_key):

    if address in coordinate_cache:
        return coordinate_cache[address]

    url = "https://dapi.kakao.com/v2/local/search/address.json"

    headers = {
        "Authorization": f"KakaoAK {api_key}"
    }

    params = {
        "query": address
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code == 200:

            result = response.json()

            if result["documents"]:

                # Kakao API
                # x = 경도(longitude)
                # y = 위도(latitude)

                x = result["documents"][0]["x"]
                y = result["documents"][0]["y"]

                coordinate_cache[address] = (x, y)

                return x, y

            else:
                print(f"주소 검색 결과 없음: {address}")
                coordinate_cache[address] = (None, None)
                return None, None

        else:
            print(
                f"API 오류: {address} / "
                f"상태코드: {response.status_code} / "
                f"응답: {response.text}"
            )

            return None, None

    except requests.exceptions.RequestException as e:

        print(f"API 요청 오류: {address} / {e}")

        return None, None


# ============================================================
# 4. CSV 파일 두 개 불러오기
# ============================================================

# ------------------------------------------------------------
# 4-1. 온통대전 가맹점 (name, address / cp949)
# ------------------------------------------------------------

ontong_path = base_dir / "place_map_template.csv"

ontong_data = pd.read_csv(
    ontong_path,
    encoding="cp949"
)

ontong_data = ontong_data.rename(
    columns={
        "name": "상호",
        "address": "주소"
    }
)

ontong_data["구분"] = "온통대전"

# 가맹점에는 휘발유 가격이 없다.
# 주유소 자료와 열을 맞추기 위해 결측값(NaN) 열을 만들어 둔다.
# pd.NA 대신 float("nan")을 쓰면 두 자료를 합칠 때 열의 자료형이 어긋나지 않는다.
ontong_data["휘발유"] = float("nan")

# ------------------------------------------------------------
# 4-2. 주유소 (오늘 날짜 폴더 / utf-8-sig)
# ------------------------------------------------------------

# 오피넷 수집 결과는 아래 위치에 날짜별로 쌓인다.
#
#   offinet/day/20260902/대전주유소_20260902.csv
#
# 엑셀의 TODAY() 처럼 실행하는 날의 날짜로 경로를 만들어 읽는다.

station_dir = base_dir / "offinet" / "day"


def find_station_file(station_dir, target_date):
    """오늘 날짜 파일을 찾고, 없으면 가장 최근 날짜 파일을 돌려준다."""

    day_text = target_date.strftime("%Y%m%d")

    today_file = station_dir / day_text / f"대전주유소_{day_text}.csv"

    if today_file.exists():
        return today_file

    # 새벽 2시 수집 전에 실행했거나 수집이 밀린 경우를 대비하여
    # 지난 날짜 폴더 중 가장 최근 파일을 찾아 쓴다.

    previous_files = sorted(
        path
        for path in station_dir.glob("*/대전주유소_*.csv")
        if path.parent.name.isdigit() and path.parent.name <= day_text
    )

    if not previous_files:
        raise FileNotFoundError(
            "주유소 자료를 찾지 못했습니다.\n"
            f"찾은 경로: {today_file}"
        )

    latest_file = previous_files[-1]

    print(
        f"오늘 날짜({day_text}) 자료가 없어 "
        f"가장 최근 자료를 사용합니다: {latest_file.name}"
    )

    return latest_file


station_path = find_station_file(station_dir, date.today())

print(f"주유소 자료: {station_path}")

station_data = pd.read_csv(
    station_path,
    encoding="utf-8-sig"
)

station_data["구분"] = "주유소"

# ------------------------------------------------------------
# 4-3. 두 자료를 하나로 합치기
# ------------------------------------------------------------

# 온통대전 가맹점을 먼저, 주유소를 뒤에 둔다.
# 뒤에 그린 주유소 마커와 가격 라벨이 위에 놓이게 하기 위함이다.

columns = ["상호", "주소", "구분", "휘발유"]

data = pd.concat(
    [
        ontong_data[columns],
        station_data[columns]
    ],
    ignore_index=True
)


# ============================================================
# 5. 주소를 좌표로 변환
# ============================================================

print(f"주소 {len(data)}건 좌표 변환을 시작합니다.")

data["x"], data["y"] = zip(
    *data["주소"].apply(
        lambda address: get_coordinates(address, api_key)
    )
)


# ============================================================
# 6. 지도 생성
# ============================================================

# 대전시청 좌표
map_center = [36.3504, 127.3845]

facility_map = folium.Map(
    location=map_center,
    zoom_start=12
)

# 지도 객체의 JavaScript 변수명
# 7-3의 Geolocation 스크립트와 9-3의 버튼 삽입 위치에 사용한다.
map_name = facility_map.get_name()


# ============================================================
# 7. 현위치 버튼과 가격 라벨 스타일
# ============================================================

# ------------------------------------------------------------
# 7-1. 스타일(CSS)
# ------------------------------------------------------------

# .fuel-price-label 은 8-2에서 주유소 마커에 붙이는
# 항상 보이는 툴팁(라벨)의 모양이다.

custom_css = """
            <style>
                #current-location {
                    position: fixed;
                    top: calc(env(safe-area-inset-top, 0px) + 12px);
                    right: calc(env(safe-area-inset-right, 0px) + 12px);
                    bottom: auto;
                    z-index: 10000;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    min-width: 104px;
                    min-height: 48px;
                    padding: 11px 16px;
                    border: 2px solid #1677ff;
                    border-radius: 10px;
                    background-color: #ffffff !important;
                    color: #111111 !important;
                    -webkit-text-fill-color: #111111 !important;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
                    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
                    font-size: 17px;
                    font-weight: 700;
                    line-height: 1.2;
                    text-align: center;
                    text-shadow: none;
                    white-space: nowrap;
                    cursor: pointer;
                    -webkit-appearance: none;
                    appearance: none;
                    -webkit-tap-highlight-color: transparent;
                    touch-action: manipulation;
                }
                #current-location:disabled {
                    opacity: 0.65;
                    cursor: wait;
                }
                .leaflet-tooltip.fuel-price-label {
                    padding: 2px 6px;
                    border: 1px solid #d93025;
                    border-radius: 6px;
                    background-color: #ffffff;
                    color: #d93025;
                    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
                    font-size: 12px;
                    font-weight: 700;
                    line-height: 1.2;
                    white-space: nowrap;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
                }
                .leaflet-tooltip.fuel-price-label::before {
                    display: none;
                }
                .ontong-pin {
                    background: transparent;
                    border: none;
                    line-height: 0;
                }
            </style>
"""

# ------------------------------------------------------------
# 7-2. 버튼 요소(HTML)
# ------------------------------------------------------------

current_location_button = (
    '<button id="current-location" type="button" '
    'aria-label="현재 위치로 이동">'
    '<span aria-hidden="true">📍</span>&nbsp;현위치</button>'
)

# ------------------------------------------------------------
# 7-3. 버튼 동작(JavaScript)
# ------------------------------------------------------------

current_location_js = f"""
            var current_location_marker = null;
            var current_location_accuracy = null;
            var current_location_button = document.getElementById("current-location");

            current_location_button.addEventListener("click", function () {{
                if (!navigator.geolocation) {{
                    alert("이 브라우저에서는 위치 기능을 사용할 수 없습니다.");
                    return;
                }}

                current_location_button.disabled = true;
                current_location_button.textContent = "위치 찾는 중…";

                navigator.geolocation.getCurrentPosition(
                    function (position) {{
                        var latitude = position.coords.latitude;
                        var longitude = position.coords.longitude;
                        var accuracy = position.coords.accuracy;
                        var location = [latitude, longitude];

                        if (current_location_marker) {{
                            {map_name}.removeLayer(current_location_marker);
                        }}
                        if (current_location_accuracy) {{
                            {map_name}.removeLayer(current_location_accuracy);
                        }}

                        current_location_accuracy = L.circle(location, {{
                            radius: accuracy,
                            color: "#1677ff",
                            weight: 1,
                            fillColor: "#1677ff",
                            fillOpacity: 0.12
                        }}).addTo({map_name});

                        current_location_marker = L.circleMarker(location, {{
                            radius: 9,
                            color: "#ffffff",
                            weight: 3,
                            fillColor: "#1677ff",
                            fillOpacity: 1
                        }}).addTo({map_name})
                          .bindPopup("현재 위치")
                          .openPopup();

                        {map_name}.setView(location, 16);
                        current_location_button.disabled = false;
                        current_location_button.innerHTML = '<span aria-hidden="true">📍</span>&nbsp;현위치';
                    }},
                    function (error) {{
                        var message = "현재 위치를 가져오지 못했습니다.";
                        if (error.code === error.PERMISSION_DENIED) {{
                            message = "위치 권한이 거부되었습니다. Safari의 웹사이트 설정에서 위치 접근을 허용해 주세요.";
                        }} else if (error.code === error.POSITION_UNAVAILABLE) {{
                            message = "현재 위치 정보를 확인할 수 없습니다.";
                        }} else if (error.code === error.TIMEOUT) {{
                            message = "위치 확인 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.";
                        }}
                        alert(message);
                        current_location_button.disabled = false;
                        current_location_button.innerHTML = '<span aria-hidden="true">📍</span>&nbsp;현위치';
                    }},
                    {{
                        enableHighAccuracy: true,
                        timeout: 15000,
                        maximumAge: 30000
                    }}
                );
            }});
"""


# ============================================================
# 8. 마커 표시
# ============================================================

# 온통대전 가맹점 마커의 모양
#
# 주유소와 같은 열기구(물방울) 모양이지만 속을 비워야 하므로
# 색이 채워진 기본 아이콘 대신 테두리만 그린 SVG를 직접 만들어 쓴다.
# fill="none" 이므로 핀 안쪽으로 지도가 그대로 보인다.

ontong_color = "#1677ff"      # 테두리 색
ontong_weight = 2             # 테두리 두께(픽셀)
ontong_width = 25             # 핀 너비(픽셀)
ontong_height = 41            # 핀 높이(픽셀)

ontong_svg = f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="{ontong_width}" height="{ontong_height}"
     viewBox="0 0 {ontong_width} {ontong_height}">
  <path d="M12.5 39.5 C12.5 39.5 23 22.3 23 12.5
           A10.5 10.5 0 1 0 2 12.5
           C2 22.3 12.5 39.5 12.5 39.5 Z"
        fill="none"
        stroke="{ontong_color}"
        stroke-width="{ontong_weight}"
        stroke-linejoin="round" />
</svg>
"""


for index, row in data.iterrows():

    x = row["x"]   # 경도
    y = row["y"]   # 위도

    if pd.isnull(x) or pd.isnull(y):
        continue

    location = [float(y), float(x)]

    place_name = row["상호"]
    category = row["구분"]

    # --------------------------------------------------------
    # 8-1. 온통대전 가맹점 : 파란색 테두리에 속이 빈 열기구 모양
    # --------------------------------------------------------

    if category == "온통대전":

        folium.Marker(
            location=location,
            popup=place_name,
            tooltip=place_name,

            # 핀 끝(아래 꼭짓점)이 실제 좌표에 놓이도록
            # icon_anchor를 아이콘 아래쪽 가운데로 맞춘다.
            icon=folium.DivIcon(
                html=ontong_svg,
                icon_size=(ontong_width, ontong_height),
                icon_anchor=(ontong_width / 2, ontong_height - 1.5),
                class_name="ontong-pin"
            )
        ).add_to(facility_map)

    # --------------------------------------------------------
    # 8-2. 주유소 : 빨간색 마커 + 휘발유 가격 라벨
    # --------------------------------------------------------

    else:

        # 휘발유를 취급하지 않거나 가격이 비어 있는 주유소가 있으므로
        # 값이 없으면 가격 라벨 없이 마커만 찍는다.

        has_price = pd.notnull(row["휘발유"])

        if has_price:
            price_text = f"{int(row['휘발유']):,}원"
            popup_text = f"{place_name}<br>휘발유 {price_text}"
        else:
            price_text = None
            popup_text = f"{place_name}<br>휘발유 가격 정보 없음"

        # permanent=True 이므로 마우스를 올리지 않아도
        # 가격 라벨이 항상 지도에 표시된다.

        if has_price:
            station_tooltip = folium.Tooltip(
                price_text,
                permanent=True,
                direction="top",
                offset=(0, -34),
                sticky=False,
                className="fuel-price-label"
            )
        else:
            station_tooltip = folium.Tooltip(place_name, sticky=True)

        folium.Marker(
            location=location,
            popup=popup_text,
            icon=folium.Icon(color="red", icon="tint"),
            tooltip=station_tooltip
        ).add_to(facility_map)


# ============================================================
# 9. 렌더링 결과에 현위치 버튼 삽입
# ============================================================

# folium이 만들어 주는 HTML 문자열에 위 7번의 CSS, HTML, JavaScript를
# 각각 정해진 자리에 끼워 넣는다.
#
#   CSS        : <head>의 지도 스타일 뒤, L_NO_TOUCH 스크립트 앞
#   HTML(버튼) : <body>의 지도 <div> 바로 뒤
#   JavaScript : 지도와 마커 생성 코드가 모두 끝난 </script> 앞
#
# 삽입 기준이 되는 문자열은 folium 템플릿에서 오는 것이므로,
# folium 버전이 올라가 기준 문자열이 사라지면 즉시 오류로 알린다.

def insert_after(html, anchor, addition):
    """anchor 문자열 바로 뒤에 addition을 끼워 넣는다."""

    if anchor not in html:
        raise RuntimeError(
            "HTML 삽입 위치를 찾지 못했습니다.\n"
            f"기준 문자열: {anchor[:60]}"
        )

    return html.replace(anchor, anchor + addition, 1)


def insert_before(html, anchor, addition):
    """anchor 문자열 바로 앞에 addition을 끼워 넣는다."""

    if anchor not in html:
        raise RuntimeError(
            "HTML 삽입 위치를 찾지 못했습니다.\n"
            f"기준 문자열: {anchor[:60]}"
        )

    return html.replace(anchor, addition + anchor, 1)


map_html = facility_map.get_root().render()

# ------------------------------------------------------------
# 9-1. 뷰포트에 viewport-fit=cover 추가
# ------------------------------------------------------------

# folium이 기본으로 넣는 뷰포트 설정에는 viewport-fit=cover가 없다.
# 아이폰 노치 영역까지 지도가 채워지도록 렌더링 결과에서 한 번 치환한다.

viewport_anchor = 'user-scalable=no" />'

if viewport_anchor not in map_html:
    raise RuntimeError("뷰포트 설정을 찾지 못했습니다.")

map_html = map_html.replace(
    viewport_anchor,
    'user-scalable=no, viewport-fit=cover" />',
    1
)

# ------------------------------------------------------------
# 9-2. 스타일(CSS)을 <head>에 삽입
# ------------------------------------------------------------

# CSS 문자열 앞뒤의 줄바꿈을 다듬어
# folium이 만든 다른 <style> 블록과 같은 간격으로 놓이게 한다.

map_html = insert_before(
    map_html,
    "            <script>\n                L_NO_TOUCH",
    custom_css.lstrip("\n") + "\n"
)

# ------------------------------------------------------------
# 9-3. 버튼 요소(HTML)를 <body>의 지도 <div> 뒤에 삽입
# ------------------------------------------------------------

map_html = insert_after(
    map_html,
    f'<div class="folium-map" id="{map_name}" ></div>',
    "\n            " + current_location_button
)

# ------------------------------------------------------------
# 9-4. 버튼 동작(JavaScript)을 </script> 앞에 삽입
# ------------------------------------------------------------

map_html = insert_before(
    map_html,
    "        \n</script>",
    current_location_js
)


# ============================================================
# 10. 지도 HTML 파일 저장 (index.html)
# ============================================================

output_file = base_dir / "index.html"

# 웹 서버에 그대로 올릴 파일이므로 줄바꿈은 LF로 통일하고,
# 파일 끝에는 줄바꿈 하나를 남긴다.

if not map_html.endswith("\n"):
    map_html = map_html + "\n"

with open(output_file, "w", encoding="utf-8", newline="\n") as f:
    f.write(map_html)


# ============================================================
# 11. 결과 요약 출력
# ============================================================

located = data["x"].notnull() & data["y"].notnull()

for category in ["온통대전", "주유소"]:

    is_category = data["구분"] == category

    total_count = int(is_category.sum())
    marker_count = int((is_category & located).sum())
    failed_count = total_count - marker_count

    print(
        f"[{category}] 전체 {total_count}건 중 "
        f"{marker_count}건 표시, {failed_count}건 좌표 변환 실패"
    )

    if failed_count:
        failed_names = data.loc[is_category & ~located, "상호"].tolist()
        print(f"[{category}] 좌표 변환 실패 목록: {failed_names}")

print(f"지도 생성 완료: {output_file}")
