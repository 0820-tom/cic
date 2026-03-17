import streamlit as st
import pandas as pd
from datetime import datetime

def process_attendance(df):
    # 1. 특정 인원 제외 (6명)
    excluded_names = ['김기돈', '여기대', '임덕상', '김효정', '김운철', '윤희주']
    if '성명' in df.columns:
        df = df[~df['성명'].isin(excluded_names)]
    
    # 2. 주말 제외
    if '요일' in df.columns:
        df = df[~df['요일'].isin(['토요일', '일요일'])]
    
    # 3. 공휴일 제외 ('공휴일' 컬럼이 비어있지 않은 경우 제외)
    if '공휴일' in df.columns:
        df = df[df['공휴일'].isna() | (df['공휴일'] == '') | (df['공휴일'].astype(str).str.lower() == 'nan')]
    
    # '휴가' 컬럼 결측치 및 문자열 'null' 처리
    if '휴가' in df.columns:
        df['휴가'] = df['휴가'].fillna('null').astype(str)
    else:
        df['휴가'] = 'null'
    
    # 출퇴근시간 파싱 ('출근시각', '퇴근시각'이 ':'나 빈칸으로 되어 있는 경우 결측치로 변환)
    df['출근_시간'] = pd.to_datetime(df['출근시각'], format='%H:%M', errors='coerce').dt.time
    df['퇴근_시간'] = pd.to_datetime(df['퇴근시각'], format='%H:%M', errors='coerce').dt.time
    
    # 기준 시간 설정 (10시, 17시)
    time_10 = datetime.strptime('10:00', '%H:%M').time()
    time_17 = datetime.strptime('17:00', '%H:%M').time()
    
    results = []
    
    for index, row in df.iterrows():
        # 연차(휴가) 사용 기록이 있는지 확인 ('null'이 아니면 연차 사용으로 간주)
        has_leave = row['휴가'].strip().lower() != 'null' and row['휴가'].strip() != ''
        
        arrival = row['출근_시간']
        departure = row['퇴근_시간']
        
        issues = []
        
        # 연차 사용 기록이 없는 경우에만 근태 이상 여부 체크
        if not has_leave:
            # 1. 출퇴근시각 확인 안 되는 경우 (둘 중 하나라도 없으면)
            if pd.isna(arrival) or pd.isna(departure):
                issues.append('출퇴근시각 누락')
            else:
                # 2. 10시 이후 출근
                if arrival >= time_10:
                    issues.append('10시 이후 출근')
                
                # 3. 17시 이전 퇴근
                if departure < time_17:
                    issues.append('17시 이전 퇴근')
                    
        # 문제가 하나라도 발견되었다면 결과 리스트에 추가
        if issues:
            results.append({
                '근무일자': row.get('근무일자', ''),
                '성명': row.get('성명', ''),
                '부서': row.get('부서', ''),
                '요일': row.get('요일', ''),
                '출근시각': row.get('출근시각', ''),
                '퇴근시각': row.get('퇴근시각', ''),
                '휴가': row.get('휴가', ''),
                '확인필요항목': ', '.join(issues)
            })
            
    return pd.DataFrame(results)

# ---------------- Streamlit UI 구성 ---------------- #
st.set_page_config(page_title="출결 분석 프로그램", layout="wide")

st.title("⏱️ 일일 근태 이상 체크 프로그램")
st.write("""
주말, 공휴일, 그리고 특정 인원을 제외한 대상자 중 
**10시 이후 출근 / 17시 이전 퇴근 / 출퇴근시각 누락** 내역(연차 미사용자 기준)을 찾아냅니다.
""")

uploaded_file = st.file_uploader("근태 기록 파일 업로드 (CSV, XLS, XLSX)", type=['csv', 'xls', 'xlsx'])

if uploaded_file is not None:
    try:
        # 파일 확장자에 따라 판다스로 읽어오기
        if uploaded_file.name.endswith('.csv'):
            # 한국어 CSV 인코딩 처리 (utf-8 -> cp949 순서로 시도)
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            # xls, xlsx 읽기
            df = pd.read_excel(uploaded_file)
            
        st.subheader("📁 원본 데이터 미리보기 (최상위 5건)")
        st.dataframe(df.head())
        
        with st.spinner("근태 데이터를 분석 중입니다..."):
            result_df = process_attendance(df)
            
        st.subheader("🚨 근태 확인 필요 대상자")
        if not result_df.empty:
            st.dataframe(result_df, use_container_width=True)
            
            # 분석 결과를 CSV로 다운로드
            csv = result_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 분석 결과 다운로드 (CSV)",
                data=csv,
                file_name='근태확인대상자.csv',
                mime='text/csv',
            )
            st.warning(f"총 {len(result_df)}건의 확인 필요 내역이 발견되었습니다.")
        else:
            st.success("🎉 모든 직원의 근태가 정상입니다. (확인 대상자 없음)")
            
    except Exception as e:
        st.error(f"파일을 처리하는 도중 오류가 발생했습니다: {e}")
