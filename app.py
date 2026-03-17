import streamlit as st
import pandas as pd
from datetime import datetime

# ---------------- Streamlit UI 기본 설정 ---------------- #
st.set_page_config(page_title="출결 분석 프로그램", layout="wide")

# 기본 제외 대상자 6명
DEFAULT_EXCLUDED = ['김기돈', '여기대', '임덕상', '김효정', '김운철', '윤희주']

st.title("⏱️ 일일 근태 이상 체크 프로그램")
st.write("""
주말, 공휴일, 그리고 **선택한 제외 대상자**를 뺀 나머지 인원 중 
**10시 이후 출근 / 17시 이전 퇴근 / 출퇴근시각 누락** 내역(연차 미사용자 기준)을 찾아냅니다.
""")

# 좌측 사이드바 구성
st.sidebar.header("⚙️ 업로드 및 설정")
uploaded_file = st.sidebar.file_uploader("근태 기록 파일 업로드", type=['csv', 'xls', 'xlsx'])

if uploaded_file is not None:
    try:
        # 파일 인코딩 및 읽기 처리
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df = pd.read_excel(uploaded_file)
            
        # ==========================================
        # 1. 예외 대상자 추가/제거 시스템
        # ==========================================
        if '성명' in df.columns:
            # 파일에 있는 모든 직원의 이름을 가져와서 선택지로 제공
            unique_names = sorted(df['성명'].dropna().unique().tolist())
        else:
            unique_names = []

        # 기본 6명 중 현재 업로드된 파일에 존재하는 사람만 기본 선택값으로 지정 (에러 방지)
        default_selection = [name for name in DEFAULT_EXCLUDED if name in unique_names]
        
        st.sidebar.subheader("🚫 예외 대상자 설정")
        st.sidebar.write("아래 상자를 클릭하여 제외할 직원을 검색하거나 추가/삭제할 수 있습니다.")
        
        excluded_names = st.sidebar.multiselect(
            "출력에서 제외할 직원",
            options=unique_names,
            default=default_selection
        )
        
        # ==========================================
        # 2. 데이터 분석 로직
        # ==========================================
        with st.spinner("근태 데이터를 분석 중입니다..."):
            
            # 사용자 설정 예외 대상자 반영
            if '성명' in df.columns:
                filtered_df = df[~df['성명'].isin(excluded_names)]
            else:
                filtered_df = df.copy()
            
            # 주말 제외
            if '요일' in filtered_df.columns:
                filtered_df = filtered_df[~filtered_df['요일'].isin(['토요일', '일요일'])]
            
            # 공휴일 제외
            if '공휴일' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['공휴일'].isna() | (filtered_df['공휴일'] == '') | (filtered_df['공휴일'].astype(str).str.lower() == 'nan')]
            
            # '휴가' 컬럼 처리 (결측치를 'null' 문자열로 통일)
            if '휴가' in filtered_df.columns:
                filtered_df['휴가'] = filtered_df['휴가'].fillna('null').astype(str)
            else:
                filtered_df['휴가'] = 'null'
            
            # 시간 파싱 (':' 만 있거나 비어있는 경우 NaT로 처리)
            filtered_df['출근_시간'] = pd.to_datetime(filtered_df['출근시각'], format='%H:%M', errors='coerce').dt.time
            filtered_df['퇴근_시간'] = pd.to_datetime(filtered_df['퇴근시각'], format='%H:%M', errors='coerce').dt.time
            
            time_10 = datetime.strptime('10:00', '%H:%M').time()
            time_17 = datetime.strptime('17:00', '%H:%M').time()
            
            results = []
            
            for index, row in filtered_df.iterrows():
                # 휴가 컬럼에 'null' 이외의 텍스트가 있으면 휴가 사용자로 간주
                has_leave = row['휴가'].strip().lower() != 'null' and row['휴가'].strip() != ''
                arrival = row['출근_시간']
                departure = row['퇴근_시간']
                issues = []
                
                # 연차 사용 기록이 없는 경우에만 근태 확인
                if not has_leave:
                    if pd.isna(arrival) or pd.isna(departure):
                        issues.append('출퇴근시각 누락')
                    else:
                        if arrival >= time_10:
                            issues.append('10시 이후 출근')
                        if departure < time_17:
                            issues.append('17시 이전 퇴근')
                                
                if issues:
                    # 사진 예시와 동일한 컬럼 구성으로 딕셔너리 생성
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
                    
            result_df = pd.DataFrame(results)

        # ==========================================
        # 3. 화면 출력 (사진 예시와 동일한 형태)
        # ==========================================
        st.subheader("🚨 근태 확인 필요 대상자")
        if not result_df.empty:
            
            # hide_index=True 옵션으로 좌측 번호를 지워 사진과 똑같이 깔끔하게 출력
            st.dataframe(result_df, hide_index=True, use_container_width=True)
            
            st.warning(f"총 {len(result_df)}건의 확인 필요 내역이 발견되었습니다.")
            
            # 분석 결과를 CSV로 다운로드
            csv = result_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 분석 결과 다운로드 (CSV)",
                data=csv,
                file_name='근태확인대상자.csv',
                mime='text/csv',
            )
        else:
            st.success("🎉 모든 직원의 근태가 정상입니다. (확인 대상자 없음)")
            
    except Exception as e:
        st.error(f"파일을 처리하는 도중 오류가 발생했습니다: {e}")
