# place_map_api_v3(clear_지오코딩)

import os
import requests
import pandas as pd
import folium
from dotenv import load_dotenv


# ============================================================
# 1. 현재 .py 파일이 있는 폴더 경로 가져오기
# ============================================================

base_dir = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 2. .env 파일에서 Kakao API Key 불러오기
# ============================================================

env_path = os.path.join(base_dir, ".env")

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

def get_coordinates(address, api_key):

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

                return x, y

            else:
                print(f"주소 검색 결과 없음: {address}")
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
# 4. CSV 파일 불러오기
# ============================================================

file_path = os.path.join(
    base_dir,
    "place_map_template.csv"
)

data = pd.read_csv(
    file_path,
    encoding="cp949"
)


# ============================================================
# 5. 주소를 좌표로 변환
# ============================================================

data["x"], data["y"] = zip(
    *data["address"].apply(
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


# ============================================================
# 7. 시설 위치 마커 표시
# ============================================================

for index, row in data.iterrows():

    facility_name = row["name"]

    x = row["x"]   # 경도
    y = row["y"]   # 위도

    if pd.notnull(x) and pd.notnull(y):

        folium.Marker(
            location=[float(y), float(x)],
            popup=facility_name,
            tooltip=facility_name
        ).add_to(facility_map)


# ============================================================
# 8. 지도 HTML 파일 저장
# ============================================================

output_file = os.path.join(
    base_dir,
    "facility_map.html"
)

facility_map.save(output_file)

print(f"지도 생성 완료: {output_file}")