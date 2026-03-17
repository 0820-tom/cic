import streamlit as st
import pandas as pd
from datetime import datetime

# ---------------- Streamlit UI 기본 설정 ---------------- #
st.set_page_config(page_title="출결 분석 프로그램", layout="wide")

DEFAULT_EXCLUDED = ['김기돈', '여기대', '임덕상', '김효정', '김운철', '윤희주']

st.title("⏱️ 일일 근태 이상 체크 프로그램 (요약 버전)")
st.write("""
주말, 공휴일, 예외 대상자 및 휴가자를 제외한 인원의 
**출근 누락 / 퇴근 누락 / 지각 / 조기퇴근** 내역을 그룹화하여 보여줍니다.
""")

st.sidebar.header("⚙️ 업로드 및 설정")
uploaded_file = st.sidebar.file_uploader("근태 기록 파일 업로드", type=['csv', 'xls', 'xlsx'])

# 시간(분) 계산 함수
def calc_late_minutes(t):
    return (t.hour * 60 + t.minute) - (10 * 60) # 10시 기준

def calc_early_minutes(t):
    return (17 * 60) - (t.hour * 60 + t.minute) # 17시 기준

def format_time_diff(m):
    if m >= 60:
        h = m // 60
        rem = m % 60
        return f"{h}시간 {rem}분" if rem > 0 else f"{h}시간"
    return f"{m}분"

if uploaded_file is not None:
    try:
        # 파일 인코딩 및 읽기
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df = pd.read_excel(uploaded_file)
            
        # 예외 대상자 설정 로직
        if '성명' in df.columns:
            unique_names = sorted(df['성명'].dropna().unique().tolist())
        else:
            unique_names = []

        default_selection = [name for name in DEFAULT_EXCLUDED if name in unique_names]
        
        st.sidebar.subheader("🚫 예외 대상자 설정")
        excluded_names = st.sidebar.multiselect(
            "출력에서 제외할 직원",
            options=unique_names,
            default=default_selection
        )
        
        with st.spinner("근태 데이터를 요약 분석 중입니다..."):
            
            if '성명' in df.columns:
                filtered_df = df[~df['성명'].isin(excluded_names)]
            else:
                filtered_df = df.copy()
            
            if '요일' in filtered_df.columns:
                filtered_df = filtered_df[~filtered_df['요일'].isin(['토요일', '일요일'])]
            
            if '공휴일' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['공휴일'].isna() | (filtered_df['공휴일'] == '') | (filtered_df['공휴일'].astype(str).str.lower() == 'nan')]
            
            if '휴가' in filtered_df.columns:
                filtered_df['휴가'] = filtered_df['휴가'].fillna('null').astype(str)
            else:
                filtered_df['휴가'] = 'null'
            
            # 카테고리별 분리된 딕셔너리
            dict_all_missing = {}
            dict_in_missing = {}
            dict_out_missing = {}
            dict_late = {}
            dict_early = {}
            
            cnt_all = cnt_in = cnt_out = cnt_late = cnt_early = 0
            
            def add_to_dict(d, name, val):
                if name not in d:
                    d[name] = []
                d[name].append(val)
            
            for index, row in filtered_df.iterrows():
                has_leave = row['휴가'].strip().lower() != 'null' and row['휴가'].strip() != ''
                if has_leave:
                    continue
                    
                name = row.get('성명', '알수없음')
                date_str = str(row.get('근무일자', ''))
                
                # 날짜에서 'n일'만 추출 (예: 2026.02.05 -> 5일)
                try:
                    clean_date = date_str.replace('-', '.').replace('/', '.')
                    day_val = int(clean_date.split('.')[-1])
                    day = f"{day_val}일"
                except:
                    day = date_str
                    
                in_time_str = str(row.get('출근시각', '')).strip()
                out_time_str = str(row.get('퇴근시각', '')).strip()
                
                no_in = (in_time_str == '' or in_time_str == ':' or 'nan' in in_time_str.lower())
                no_out = (out_time_str == '' or out_time_str == ':' or 'nan' in out_time_str.lower())
                
                # 1. 누락 여부 분류 (출근/퇴근 각각 따로)
                if no_in and no_out:
                    add_to_dict(dict_all_missing, name, f"{day}, 출퇴근 모두 누락")
                    cnt_all += 1
                elif no_in:
                    add_to_dict(dict_in_missing, name, f"{day}, 출근 누락")
                    cnt_in += 1
                elif no_out:
                    add_to_dict(dict_out_missing, name, f"{day}, 퇴근 누락")
                    cnt_out += 1
                else:
                    # 2. 지각/조기퇴근 분류
                    try:
                        in_time = datetime.strptime(in_time_str, '%H:%M').time()
                        out_time = datetime.strptime(out_time_str, '%H:%M').time()
                        time_10 = datetime.strptime('10:00', '%H:%M').time()
                        time_17 = datetime.strptime('17:00', '%H:%M').time()
                        
                        if in_time >= time_10:
                            mins = calc_late_minutes(in_time)
                            add_to_dict(dict_late, name, f"{day}, {format_time_diff(mins)} 지각")
                            cnt_late += 1
                            
                        if out_time < time_17:
                            mins = calc_early_minutes(out_time)
                            add_to_dict(dict_early, name, f"{day}, {format_time_diff(mins)} 조기퇴근")
                            cnt_early += 1
                    except Exception:
                        pass
                        
            # 문자열 조합 함수 (예: AAA (1일, 퇴근 누락 / 2일, 퇴근 누락))
            def build_str(d):
                if not d:
                    return "없음"
                return ",  ".join([f"{k} ({' / '.join(v)})" for k, v in d.items()])

            # 표 생성을 위한 데이터 조립 (행을 5개로 완벽히 분리)
            summary_data = [
                {
                    "구분": "출근 누락",
                    "인원/건수": f"{len(dict_in_missing)}명 ({cnt_in}건)",
                    "상세내역": build_str(dict_in_missing)
                },
                {
                    "구분": "퇴근 누락",
                    "인원/건수": f"{len(dict_out_missing)}명 ({cnt_out}건)",
                    "상세내역": build_str(dict_out_missing)
                },
                {
                    "구분": "출퇴근 모두 누락",
                    "인원/건수": f"{len(dict_all_missing)}명 ({cnt_all}건)",
                    "상세내역": build_str(dict_all_missing)
                },
                {
                    "구분": "지각 (10시 이후)",
                    "인원/건수": f"{len(dict_late)}명 ({cnt_late}건)",
                    "상세내역": build_str(dict_late)
                },
                {
                    "구분": "조기퇴근 (17시 이전)",
                    "인원/건수": f"{len(dict_early)}명 ({cnt_early}건)",
                    "상세내역": build_str(dict_early)
                }
            ]
            
            summary_df = pd.DataFrame(summary_data)

        # ==========================================
        # 화면 출력 (요약표)
        # ==========================================
        st.subheader("📋 근태 이상 요약 결과")
        st.dataframe(
            summary_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "구분": st.column_config.TextColumn("구분", width="small"),
                "인원/건수": st.column_config.TextColumn("인원 (건수)", width="small"),
                "상세내역": st.column_config.TextColumn("상세내역", width="large")
            }
        )
        
        csv = summary_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 요약 결과 다운로드 (CSV)",
            data=csv,
            file_name='근태요약결과.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"파일을 처리하는 도중 오류가 발생했습니다: {e}")
