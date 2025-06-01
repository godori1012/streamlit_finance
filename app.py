import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go

# 날짜 포맷
today_str = datetime.now().strftime("%Y%m%d")
st.set_page_config(layout="wide")
st.title("\U0001F4C8 주식 종목")

baseurl = "https://finance.naver.com/sise/entryJongmok.nhn?&page="

# --------------------- 크롤링 함수 정의 ---------------------
def crawl_stock_page(page_num: int):
    url = baseurl + str(page_num)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "lxml")

    table = soup.find("table", class_="type_1")
    rows = table.find_all("tr")[2:]

    data = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) != 7:
            continue

        name = cols[0].text.strip()
        price = cols[1].text.strip().replace(",", "")

        diff_tag = cols[2].select_one("span.tah")
        diff = diff_tag.text.strip().replace(",", "") if diff_tag else "0"
        em_tag = cols[2].find("em")
        if em_tag and "bu_pdn" in em_tag.get("class", []):
            diff = f"-{diff}"
        elif em_tag and "bu_pup" in em_tag.get("class", []):
            diff = f"{diff}"
        else:
            diff = "0"

        rate = cols[3].text.strip().replace("%", "")
        volume = cols[4].text.strip().replace(",", "")
        value = cols[5].text.strip()
        market_cap = cols[6].text.strip()

        data.append([name, price, diff, rate, volume, value, market_cap])

    df = pd.DataFrame(data, columns=["종목명", "현재가", "전일비", "등락률", "거래량", "거래대금", "시가총액"])

    for col in ["현재가", "전일비", "등락률", "거래량"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

    filename = f"{today_str}_page_{page_num}.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    return filename

# --------------------- 기술 지표 계산 함수 ---------------------
def calculate_rsi(df, period=14):
    delta = df["현재가"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(df):
    exp1 = df["현재가"].ewm(span=12, adjust=False).mean()
    exp2 = df["현재가"].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

# --------------------- 사이드바 ---------------------
with st.sidebar:
    st.markdown("### ⬇️ 페이지 선택 ⬇️")

    page_number = st.number_input("\U0001F4C4 페이지 번호", min_value=1, step=1, value=1)
    crawl = st.button("크롤링 시작")
    st.sidebar.write("")

    st.write(f"크롤링 url: {baseurl}{page_number}")

    st.sidebar.write("")
    data_dir = Path(".")
    file_list = sorted([f.name for f in data_dir.glob(f"{today_str}_page_*.csv")])
    selected_file = st.selectbox("\U0001F4C1 다운로드된 파일", file_list if file_list else ["파일 없음"])

if crawl:
    saved_filename = crawl_stock_page(page_number)
    st.success(f"✅ {saved_filename} 저장 완료!")
    st.rerun()

# --------------------- 메인 콘텐츠 ---------------------
if selected_file and selected_file != "파일 없음":
    df_loaded = pd.read_csv(selected_file)
    df_loaded.columns = df_loaded.columns.str.strip()

    tab1, tab2 = st.tabs(["\U0001F4CA 차트", "\U0001F4C4 데이터"])

    with tab2:
        st.markdown("#### 주식 데이터")

        # 🔽 종목 필터와 정렬 UI 구성
        col_filter, col_divider, col_sort, col_order = st.columns([2, 0.1, 2, 2])

        with col_filter:
            filter_option = st.radio("종목 필터", ["전체", "상승", "하락"], horizontal=True)

        with col_divider:
            st.markdown("<div style='border-left: 1px solid #666; height: 48px; margin-top: 28px;'></div>", unsafe_allow_html=True)

        with col_sort:
            sort_column = st.selectbox(
                "정렬 항목 선택",
                ["선택 안 함", "종목명", "현재가", "전일비", "등락률", "거래량", "시가총액"]
            )

        with col_order:
            sort_order = st.radio(" ", ["오름차순", "내림차순"], horizontal=True)

        df_display = df_loaded.copy()

        # 🔍 필터 적용
        if filter_option == "상승":
            df_display = df_display[df_display["등락률"] > 0]
        elif filter_option == "하락":
            df_display = df_display[df_display["등락률"] < 0]

        sort_col_map = {
            "현재가": "현재가",
            "전일비": "전일비",
            "등락률": "등락률",
            "거래량": "거래량",
            "거래대금": "거래대금",
            "시가총액": "시가총액",
        }

        if sort_column != "선택 안 함":
            if sort_column == "종목명":
                df_display = df_display.sort_values(
                    by="종목명",
                    ascending=(sort_order == "오름차순")
                )
            else:
                col_name = sort_col_map.get(sort_column, sort_column)
                try:
                    df_display["_sort_val"] = df_display[col_name].astype(str).str.replace(",", "").astype(float)
                    df_display = df_display.sort_values(
                        by="_sort_val",
                        ascending=(sort_order == "오름차순")
                    ).drop(columns=["_sort_val"])
                except Exception as e:
                    st.warning(f"정렬 중 오류 발생: {e}")

        # ✨ 스타일링 함수
        def style_diff(val):
            try:
                val = float(val)
                if val > 0:
                    return f'<span style="color:red">▲ {int(val):,}</span>'
                elif val < 0:
                    return f'<span style="color:blue">▼ {abs(int(val)):,}</span>'
                else:
                    return f'<span style="color:gray">● 0</span>'
            except:
                return val

        def style_rate(val):
            try:
                val = float(val)
                color = "red" if val > 0 else "blue" if val < 0 else "gray"
                sign = "+" if val > 0 else "-" if val < 0 else ""
                return f'<span style="color:{color}">{sign}{abs(val):.2f}%</span>'
            except:
                return val

        def format_with_comma(val):
            try:
                return f"{int(val):,}"
            except:
                return val

        # ✨ 스타일 적용
        df_display["전일비"] = df_display["전일비"].apply(style_diff)
        df_display["등락률"] = df_display["등락률"].apply(style_rate)
        df_display["현재가"] = df_display["현재가"].apply(format_with_comma)
        df_display["거래량"] = df_display["거래량"].apply(format_with_comma)

        # 📋 HTML 렌더링
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

    with tab1:
        chart_type = st.selectbox("차트 종류 선택", ["라인 차트", "파이 차트"])
        st.markdown("#### ✓ 주요 수치 시각화")

        if chart_type == "라인 차트":
            cols = ["현재가", "거래량", "등락률"]
            valid = [c for c in cols if c in df_loaded.columns]
            st.line_chart(df_loaded.set_index("종목명")[valid])

        elif chart_type == "파이 차트":
            try:
                df_loaded["시가총액 (숫자)"] = df_loaded["시가총액"].astype(str).str.replace(",", "").astype(float)
                top5 = df_loaded.sort_values(by="시가총액 (숫자)", ascending=False).head(5)
                fig = go.Figure(data=[go.Pie(labels=top5["종목명"], values=top5["시가총액 (숫자)"])])
                fig.update_traces(textinfo="percent+label")
                fig.update_layout(title="시가총액 Top 5")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.warning(f"파이차트를 그릴 수 없습니다: {e}")

else:
    st.info("\U0001F448 좌측에서 페이지를 선택하거나 크롤링을 실행하세요.")
