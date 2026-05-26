import streamlit as st
import json
import os
import fitz  # PyMuPDF
from datetime import datetime
import io
from PIL import Image
import gdown
import requests
import base64

# 🌟 구글 드라이브 파일 ID 사전 등록 구역
PDF_LINKS = {
    "4_1_수학": "18uznawqJvSEYUGOSqbW4gQ9is6jJ7iuL",  
    "6_2_수학": "11llBJBHbszhvgb7wxB2WANYkNMGaOgYK",
}

try:
    from streamlit_cropper import st_cropper
    HAS_CROPPER = True
except ImportError:
    HAS_CROPPER = False

LOG_FILE = "study_log.json"
PROGRESS_FILE = "student_progress.json"  
QUESTION_DIR = "questions"

if not os.path.exists(QUESTION_DIR): 
    os.makedirs(QUESTION_DIR)

st.set_page_config(page_title="지역아동센터 학습관리", layout="centered")

# 🎨 분수 입력을 위한 커스텀 디자인 (CSS)
st.markdown("""
<style>
    /* 분수 전체를 감싸는 컨테이너 */
    .fraction-container {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 15px;
        background-color: #f9f9f9;
        border-radius: 15px;
        border: 1px dashed #ccc;
        width: fit-content;
    }
    
    /* 자연수 입력 칸 테두리 (연두색) */
    div[data-testid="column"]:nth-of-type(1) .stTextInput input {
        border: 3px solid #99ff99 !important;
        font-size: 24px !important;
        text-align: center !important;
    }
    
    /* 분자 입력 칸 테두리 (빨간색) */
    .num-box .stTextInput input {
        border: 3px solid #ff9999 !important;
        font-size: 20px !important;
        text-align: center !important;
    }
    
    /* 분모 입력 칸 테두리 (하늘색) */
    .den-box .stTextInput input {
        border: 3px solid #99ccff !important;
        font-size: 20px !important;
        text-align: center !important;
    }

    /* 분수 가로선 */
    .fraction-line {
        width: 80px;
        height: 4px;
        background-color: #333;
        margin: 5px 0;
        border-radius: 2px;
    }
    
    /* 텍스트 라벨 숨기기 (깔끔하게) */
    .stTextInput label {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

if 'sys_error' in st.session_state and st.session_state['sys_error']:
    st.error(st.session_state['sys_error'])

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: 
            return json.load(f)
    return {} if "progress" in file_path else []

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    try:
        if "GITHUB_TOKEN" in st.secrets:
            token, repo = st.secrets["GITHUB_TOKEN"], "wlsgh233-source/center-study-"
            url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            sha = None
            res = requests.get(url, headers=headers)
            if res.status_code == 200: sha = res.json().get("sha")
            content_str = json.dumps(data, ensure_ascii=False, indent=4)
            encoded_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
            payload = {"message": f"🤖 자동 저장: {file_path}", "content": encoded_content}
            if sha: payload["sha"] = sha
            requests.put(url, headers=headers, json=payload)
    except Exception as e:
        st.session_state['sys_error'] = f"❌ 깃허브 저장 오류: {e}"

def is_correct(user_ans, correct_ans, match_type="exact"):
    if not user_ans: return False
    def clean(s):
        s = str(s).strip().lower()
        for char in [".", "?", "!", ",", "°", " ", "\n"]: s = s.replace(char, "")
        return s
    if match_type == "fraction":
        def clean_f(s): return "0" if not s.strip() else s.strip()
        return [clean_f(x) for x in str(user_ans).split("|")] == [clean_f(x) for x in str(correct_ans).split("|")]
    if match_type == "keyword":
        u = clean(user_ans)
        return any(clean(k) in u for k in correct_ans.replace("/", ",").split(",") if clean(k))
    u, c = [clean(x) for x in str(user_ans).split("|") if clean(x)], [clean(x) for x in str(correct_ans).split("|") if clean(x)]
    return sorted(u) == sorted(c)

def download_pdf_from_drive(pdf_key):
    path = f"{pdf_key}.pdf"
    if not os.path.exists(path) and pdf_key in PDF_LINKS:
        with st.spinner("☁️ 교재 다운로드 중..."):
            gdown.download(f'https://drive.google.com/uc?id={PDF_LINKS[pdf_key]}', path, quiet=False)
    return path

def extract_cropped_page(pdf_path, page_num, crop, q_id):
    if not os.path.exists(pdf_path): return None
    doc = fitz.open(pdf_path)
    if page_num >= len(doc): return None
    page = doc[page_num]
    rect = page.rect
    crop_rect = fitz.Rect(rect.width*(crop[2]/100), rect.height*(crop[0]/100), rect.width*(crop[3]/100), rect.height*(crop[1]/100))
    return page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=crop_rect).tobytes("png")

if 'combo' not in st.session_state: st.session_state['combo'] = 0
if 'wrong_list' not in st.session_state: st.session_state['wrong_list'] = []

menu = st.sidebar.selectbox("메뉴 선택", ["✍️ 학생 문제 풀기", "🛠️ 그림 자르기 조절기", "🔒 관리자 대시보드"])

if menu == "✍️ 학생 문제 풀기":
    st.title("🏫 지역아동센터 온라인 교실")
    name = st.text_input("너의 이름을 입력해줘", key="student_name_input").strip()
    if name:
        st.success(f"🎒 {name} 어린이, 화이팅!")
        col1, col2, col3 = st.columns(3)
        g = col1.selectbox("학년", [1,2,3,4,5,6], index=5)
        s = col2.selectbox("학기", [1,2], index=1)
        sub = col3.selectbox("과목", ["국어","수학","사회","과학"], index=1)
        
        subj_key = f"{g}_{s}_{sub}"
        q_file = os.path.join(QUESTION_DIR, f"{subj_key}.json")
        
        if st.button("📝 공부 시작하기"):
            qs = load_data(q_file)
            if qs:
                prog = load_data(PROGRESS_FILE).get(name, {}).get(subj_key, 0)
                st.session_state['active_qs'] = [q for q in qs if q['id'] > prog]
                st.session_state['exam_on'] = True
                st.session_state['subj_key'] = subj_key

        if st.session_state.get('exam_on'):
            pdf_p = download_pdf_from_drive(subj_key)
            active = st.session_state.get('active_qs', [])
            if active:
                p_nums = sorted(list(set([q['page'] for q in active])))
                sel_p = st.selectbox("📖 페이지 선택", p_nums)
                st.markdown("---")
                
                curr_qs = [q for q in active if q['page'] == sel_p and q.get('type') != 'concept']
                user_ans = {}
                
                for q in curr_qs:
                    st.write(f"**Q. {q['question']}**")
                    img = extract_cropped_page(pdf_p, q['page'], q.get('crop', [0,100,0,100]), q['id'])
                    if img: st.image(img)
                    
                    # 🌟 [아이들용 분수 시각화 UI]
                    if q.get('match_type') == "fraction":
                        st.write("▼ 분수 정답 입력")
                        c_nat, c_frac = st.columns([1, 2])
                        with c_nat:
                            v_nat = st.text_input("자연수", key=f"n_{q['id']}", placeholder="자연수").strip()
                        with c_frac:
                            v_num = st.text_input("분자", key=f"u_{q['id']}", placeholder="분자").strip()
                            st.markdown('<div class="fraction-line"></div>', unsafe_allow_html=True)
                            v_den = st.text_input("분모", key=f"d_{q['id']}", placeholder="분모").strip()
                        user_ans[q['id']] = f"{v_nat}|{v_num}|{v_den}"
                    else:
                        n_a = q.get('num_ans', 1)
                        if n_a > 1:
                            ans_cols = st.columns(n_a)
                            user_ans[q['id']] = "|".join([ans_cols[i].text_input(f"답{i+1}", key=f"a_{q['id']}_{i}").strip() for i in range(n_a)])
                        else:
                            user_ans[q['id']] = st.text_input("정답 입력", key=f"a_{q['id']}").strip()
                    st.markdown("---")
                
                if st.button("💾 제출 및 채점"):
                    if st.text_input("선생님 확인 비밀번호", type="password") == "0094":
                        correct, total = 0, len(curr_qs)
                        wrong = []
                        for q in curr_qs:
                            if is_correct(user_ans[q['id']], q['answer'], q.get('match_type')): correct += 1
                            else: wrong.append(q)
                        
                        score = int(correct/total*100)
                        st.success(f"📊 점수: {score}점!")
                        
                        # 로그 저장
                        logs = load_data(LOG_FILE)
                        logs.append({"날짜": datetime.now().strftime("%Y-%m-%d"), "이름": name, "과목": subj_key, "점수": f"{score}점"})
                        save_data(LOG_FILE, logs)
                        
                        if score == 100:
                            p_data = load_data(PROGRESS_FILE)
                            if name not in p_data: p_data[name] = {}
                            p_data[name][subj_key] = max(p_data[name].get(subj_key, 0), max([q['id'] for q in curr_qs]))
                            save_data(PROGRESS_FILE, p_data)
                            st.balloons()
                        st.rerun()

elif menu == "🛠️ 그림 자르기 조절기":
    st.title("✂️ 문제집 자르기 도구")
    if st.text_input("선생님 비번", type="password") == "0094":
        col1, col2, col3 = st.columns(3)
        g, s, sub = col1.selectbox("학년", [1,2,3,4,5,6], index=5), col2.selectbox("학기", [1,2], index=1), col3.selectbox("과목", ["국어","수학","사회","과학"], index=1)
        subj_key = f"{g}_{s}_{sub}"
        pdf_p = download_pdf_from_drive(subj_key)
        
        if os.path.exists(pdf_p):
            doc = fitz.open(pdf_p)
            p_idx = st.number_input("PDF 페이지", 0, len(doc)-1, 0)
            q_idx = st.number_input("문제 번호", 1, 50, 1)
            
            st.markdown("### 🏷️ 문제 설정")
            m_type = st.radio("채점 방식", ["일반 일치", "키워드 포함", "분수 입력 (자연수|분자|분모)"])
            m_key = "fraction" if "분수" in m_type else ("keyword" if "키워드" in m_type else "exact")
            
            # 🌟 [선생님용 정답 입력 UI]
            if m_key == "fraction":
                st.info("💡 정답을 [자연수|분자|분모] 형식으로 입력하세요. (예: 1|2|7)")
                ans = st.text_input("분수 정답 입력", value="0|0|0")
            else:
                ans = st.text_input("정답 입력")

            # 자르기 도구
            img_full = Image.open(io.BytesIO(doc[p_idx].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")))
            crop_res = st_cropper(img_full, realtime_update=True, box_color='#FF0000', return_type='both')
            
            if st.button("💾 문제 저장"):
                w, h = img_full.size
                b = crop_res[1]
                final_crop = [int(b['top']/h*100), int((b['top']+b['height'])/h*100), int(b['left']/w*100), int((b['left']+b['width'])/w*100)]
                
                q_file = os.path.join(QUESTION_DIR, f"{subj_key}.json")
                qs = load_data(q_file)
                new_q = {"id": p_idx*100+q_idx, "question": f"{p_idx}쪽 {q_idx}번", "page": p_idx, "crop": final_crop, "answer": ans, "match_type": m_key}
                
                # 중복 제거 후 추가
                qs = [q for q in qs if q['id'] != new_q['id']]
                qs.append(new_q)
                save_data(q_file, sorted(qs, key=lambda x: x['id']))
                st.success("✅ 저장 완료!")

elif menu == "🔒 관리자 대시보드":
    st.title("🔒 관리자 대시보드")
    if st.text_input("비밀번호", type="password") == "0094":
        st.write("### 🏆 최근 학습 기록")
        st.table(load_data(LOG_FILE)[::-1])
