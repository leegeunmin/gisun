import json
import random, os, math
import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from openai import OpenAI
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium  # pip install folium streamlit-folium

load_dotenv()

# 환경변수에서 API 키 가져오기
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("🚨 ERROR: 'OPENAI_API_KEY'를 찾을 수 없습니다! 경찰서 담당자에게 문의해주시기 바랍니다.")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=api_key)

def get_ai_response(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 기동순찰대원 순찰 시 필요한 사항을 안내해주는 안내자입니다."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0
    )
    return response.choices[0].message.content

# CSV 파일 경로 및 데이터 로드 함수
CSV_FILE_PATH = "gisun.csv"

def load_patrol_locations_from_csv(file_path):
    df = pd.read_csv(file_path)
    required_columns = ["행정동", "순찰장소", "address", "description", "중점 활동사항"]
    if not all(col in df.columns for col in required_columns):
        st.error(f"CSV 파일에 필수 열({', '.join(required_columns)})이 누락되었습니다.")
        return None
    patrol_data = {}
    for _, row in df.iterrows():
        team = row["행정동"]
        location = row["순찰장소"]
        if team not in patrol_data:
            patrol_data[team] = {}
        patrol_data[team][location] = {
            "address": row["address"],
            "description": row["description"],
            "중점 활동사항": row["중점 활동사항"]
        }
    return patrol_data

patrol_locations = load_patrol_locations_from_csv(CSV_FILE_PATH)
if not patrol_locations:
    st.error("CSV 파일을 로드하는 데 실패했습니다. 파일 형식 또는 경로를 확인하세요.")
    st.stop()

# 캐싱 처리 및 timeout 증가 (10초)로 지오코딩 함수
@st.cache_data(show_spinner=False)
def geocode_address(address):
    geolocator = Nominatim(user_agent="geoapi", timeout=10)
    try:
        location = geolocator.geocode(
            address,
            exactly_one=True,
            bounded=True,
            country_codes="kr",
            language="ko"
        )
        if location:
            return {"lat": location.latitude, "lon": location.longitude}
        else:
            st.warning(f"주소를 찾을 수 없습니다: {address}")
            return None
    except Exception as e:
        st.error(f"지오코딩 중 오류 발생: {e}")
        return None

# 페이지 설정 및 CSS/JS (모바일 selectbox의 키보드 노출 방지)
st.set_page_config(
    page_title="고양경찰서 범죄 취약지 안내",
    page_icon="🚔",
    layout="centered"
)

dark_mode_toggle = st.checkbox("다크모드 전환", value=False)
if dark_mode_toggle:
    text_color = "white"
    bg_color = "#333333"
else:
    text_color = "black"
    bg_color = "white"

st.markdown(f"""
    <style>
    body {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    .main .block-container {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    /* st_folium 주변 여백 제거 */
    .element-container, .stFolio, .stBlock {{
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }}
    iframe {{
        display: block;
        margin: 0 auto !important;
    }}
    #map_container {{
        margin: 0px !important;
        padding: 0px !important;
    }}
    /* selectbox 입력창 클릭 시 키보드 표시 방지 */
    [data-baseweb="select"] input {{
        pointer-events: none !important;
        caret-color: transparent !important;
    }}
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        var inputs = document.querySelectorAll('[data-baseweb="select"] input');
        inputs.forEach(function(el) {{
            el.setAttribute('readonly', true);
            el.setAttribute('onfocus', 'this.blur()');
            el.addEventListener('touchstart', function(e) {{
                e.preventDefault();
                this.blur();
            }});
        }});
    }});
    </script>
""", unsafe_allow_html=True)

st.markdown(
    f"""
    <div style="text-align: center; font-size: 26px; color: {text_color}; margin-top: 20px;">
        <b>👮고양경찰서 취약지 App👮‍♂️</b>
    </div>
    """, unsafe_allow_html=True)

st.markdown(
    f"""
    <div style="text-align: center; font-size: 17px; color: {text_color}; margin-top: 20px;">
        <b>고양경찰서 순찰 필요지역 안내</b><br>
        4월 범죄예방 전략회의 시 강조사항<br>
        무인점포 절도예방, 야간 취약지역을 적극적으로 확인해주시기 바랍니다.
    </div>
    """, unsafe_allow_html=True)
st.markdown("---")

# 순찰 장소 추천 인터페이스
if patrol_locations:
    st.markdown(
        f"""
        <div style="text-align: center; font-size: 24px; color: {text_color}; margin-top: 5px;">
            <b>✅ 배치된 지역을 선택해주세요</b>
        </div>
        """, unsafe_allow_html=True)

    team_option = ["-배치된 지역을 선택해주세요-"] + list(patrol_locations.keys())
    selected_team = st.selectbox(" ", options=team_option, index=0)
    
    if selected_team != "-배치된 지역을 선택해주세요-":
        locations = list(patrol_locations[selected_team].keys())
    else:
        locations = []
        
    if selected_team != "-배치된 지역을 선택해주세요-":
        selected_location = st.selectbox("고양경찰서 선정 활동 필요지역 선택", options=locations)

        if selected_location:
            info = patrol_locations[selected_team][selected_location]
            st.markdown(f"<h3 style='color: {text_color};'>🗺️순찰 필요 지역</h3>", unsafe_allow_html=True)
            
            # 주소 지오코딩 (캐시 사용, timeout 10초)
            coords = geocode_address(info['address'])
            if coords:
                center_lat = coords['lat']
                center_lon = coords['lon']
                              
                # 지도 생성 (중심 좌표와 고정 줌)
                tile_provider = "OpenStreetMap"
                m = folium.Map(
                    location=[center_lat, center_lon],
                    zoom_start=16,
                    tiles=tile_provider
                )
                # 300m 반경 원 추가
                folium.Circle(
                    location=[center_lat, center_lon],
                    radius=300,
                    color='red',
                    weight=2,
                    fill=True,
                    fill_opacity=0.2
                ).add_to(m)

                # 중심 좌표에 마커 추가
                folium.Marker(
                    location=[center_lat, center_lon],
                    icon=folium.Icon(color='blue', icon='info-sign'),
                    popup="중심 주소"
                ).add_to(m)
                
                           
                # st_folium 호출 (key는 고정)
                st.markdown("<div id='map_container'>", unsafe_allow_html=True)
                st_folium(m, width=700, height=400, key="my_map")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("주소 지오코딩 실패로 지도 표시 불가.")
            st.markdown(f"""
                <div style="text-align: left; font-size: 25px; color: {text_color}; margin-top: 10px;">
                    <b>📌 장소명</b>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
                <div style="text-align: center; font-size: 20px; color: {text_color}; margin-top: 5px;">
                    <b>{selected_location}</b>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown(
                f"""
                <div style="text-align: left; font-size: 25px; color: {text_color}; margin-top: 20px;">
                    <b>🌟 고양서 CPO 데이터 분석 결과</b>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(info['description'])
            st.markdown(
                f"""
                <div style="text-align: left; font-size: 25px; color: {text_color}; margin-top: 20px;">
                    <b>🔍 기동순찰대 활동 참고사항(AI제작) </b>
                </div>
                """, unsafe_allow_html=True)
            st.info("💡AI 활용으로 답변에 오류가 있을 수 있습니다")
            prompt = f"""
            <역할부여>
            당신은 기동순찰대(경찰관) 순찰 활동 시 중점 활동사항을 제작해주는 안내자입니다.
            <기동순찰대 임무>
            기동순찰대의 업무는 
                1. 범죄 취약지 및 다중운집시설 등 범죄 발생이 우려되거나 치안 수요가 예상되는 지역의 범죄예방 및 위험방지를 위한 순찰
                2. 검문검색을 통한 범법자 검거
                3.「경범죄처벌법」 및 「도로교통법」 등에 규정된 범칙금 부과 대상인 기초질서위반행위의 단속
                4. 중요 범죄 및 재해ㆍ재난 등 관할구역 내 주요 상황 발생 시 현장 대응
                5. 간첩, 테러, 전시·사변 또는 이에 준하는 국가비상사태의 발생 및 선거·경호 등 범국가적 치안수요에 대한 지원
                6. 주요 치안수요 발생시 시·도경찰청 각 부서와 경찰서에 대한 업무지원
                7. 관할구역 내 범죄취약요소 진단
                8. 범죄예방을 위한 홍보 및 타 기관 등과의 협력 치안 활동
                9. 그 밖에 경찰청장 또는 시ㆍ도경찰청장이 필요하다고 인정하는 사항
            에 해당합니다.
            <설명내용>
            {selected_location}에서 기동순찰대 근무자가 순찰할 때 필요한 사항을 상세히 설명해주세요.
            지역적 특성 {info['description']}에 입력된 내용을 바탕으로 필요사항을 설명해주세요.
            순찰 시 범죄취약지역, 방범시설 부족지역을 발견하면 고양경찰서 CPO(경위 이근민, 순경 김재원)에게 아래의 파란색 링크를 통해 통보를 부탁드린다라는 내용을 꼭 포함해주세요
            최초 제목을 사용할때는 {selected_team}을 포함시켜주세요.
            
            [유의사항]
            순찰 시 유의사항을 최대 5개까지만 안내해주고 총 500자 내로 문장을 완결지어야 합니다. 
            또한 기동순찰대 임무안에 있는 내용만 제시해줘야 합니다.
            """
            response = get_ai_response(prompt)
            st.info(response)

            st.markdown(
                f"""
                <div style="text-align: left; font-size: 30px; color: {text_color}; margin-top: 20px;">
                    <b>🏚️ 취약지역 통보 </b>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="text-align: center; font-size: 16px; color: {text_color}; margin-top: 20px;">
                    <b>아래의 링크를 통해 고양경찰서 CPO에게<br>
                    취약지역을 통보해주세요.<br>
                    <a href="https://open.kakao.com/o/scgaTwdh" target="_blank" style="color: blue; font-weight: bold;">👉 고양경찰서 범죄예방진단팀</a><br>
                    </b>
                </div>
                """, unsafe_allow_html=True)

            st.markdown(
                f"""
                <div style="text-align: left; font-size: 30px; color: {text_color}; margin-top: 20px;">
                    <b>❓문의사항 </b>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="text-align: center; font-size: 16px; color: {text_color}; margin-top: 20px;">
                    <b>고양경찰서 관내 근무 중 필요한 사항이 있으시다면<br>
                    CPO 이근민 경위(031-930-5143)<br>
                    연락바랍니다.</b>
                </div>
                """, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    f"""
    <div style="text-align: center; font-size: 16px; color: {text_color}; margin-top: 20px;">
        <b> 고양경찰서 범죄예방대응과에서 제작한 사이트입니다.<br>
        AI를 활용하여 답변에 오류가 발생할 수 있습니다.</b>
    </div>
    """, unsafe_allow_html=True)