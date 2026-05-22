import streamlit as st
import json
import os
import fitz
from datetime import datetime
import io
from PIL import Image
import gdown

# 💡 구글 드라이브 ID를 여기 정확히 채워주세요!
PDF_LINKS = {
    "6_1_수학": "여기에_6학년1학기_수학_PDF_ID를_넣으세요",
    "6_2_수학": "여기에_6학년2학기_수학_PDF_ID를_넣으세요",
    "4_1_수학": "18uznawqJvSEYUGOSqbW4gQ9is6jJ7iuL",
}

# ... (중략: 기존 로직은 동일) ...

# 📝 메뉴 구성을 이렇게 학기까지 촘촘하게 바꿨습니다.
col1, col2, col3, col4 = st.columns(4)
with col1: selected_grade = st.selectbox("학년", [1, 2, 3, 4, 5, 6], index=5)
with col2: selected_semester = st.selectbox("학기", [1, 2])
with col3: selected_subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어"], index=1)
with col4: st.write("선택 완료")

# 💡 여기서 학기까지 고려해서 파일 이름을 매칭합니다.
subject_key = f"{selected_grade}_{selected_semester}_{selected_subject}"
pdf_lookup_key = f"{selected_grade}_{selected_semester}_{selected_subject}" 

# ... (중략) ...

# 🔍 파일 다운로드 함수도 학기 구분을 타게 수정했습니다.
def download_pdf_from_drive(pdf_key):
    pdf_file_path = f"{pdf_key}.pdf"
    if not os.path.exists(pdf_file_path):
        if pdf_key in PDF_LINKS:
            with st.spinner(f"☁️ {pdf_key} 교재를 불러오는 중..."):
                url = f'https://drive.google.com/uc?id={PDF_LINKS[pdf_key]}'
                gdown.download(url, pdf_file_path, quiet=False)
        else:
            st.error(f"⚠️ 코드에 등록된 이름: '{pdf_key}'가 PDF_LINKS 목록에 없습니다! 코드를 확인하세요.")
            return None
    return pdf_file_path
