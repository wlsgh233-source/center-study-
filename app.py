import streamlit as st
import json
import os
import fitz  # PyMuPDF
from datetime import datetime
import io
from PIL import Image
import gdown

# 🌟 [중요] 구글 드라이브 파일 ID 사전 등록 구역
# 학년_학기_과목 형식으로 매칭되도록 구조를 완전히 일치시켰습니다.
PDF_LINKS = {
    "4_1_수학": "18uznawqJvSEYUGOSqbW4gQ9is6jJ7iuL",  # 선생님이 주신 4학년 수학 파일 ID
    "6_1_수학": "여기에_6학년_1학기_수학_구글드라이브_ID를_넣으세요",
    "6_2_수학": "여기에_6학년_2학기_수학_구글드라이브_ID를_넣으세요",
    # 다른 학년/학기가 추가되면 아래에 똑같은 방식으로 줄줄이 추가하시면 됩니다!
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

# 구글 드라이브에서 PDF를 안전하게 다운로드하는 함수
def download_pdf_from_drive(pdf_key):
    pdf_file_path = f"{pdf_key}.pdf"
    if not os.path.exists(pdf_file_path):
        if pdf_key in PDF_LINKS:
            with st.spinner(f"☁️ {pdf_key} 교재를 구글 드라이브에서 가져오는 중... (최초 1회만)"):
                url = f'https://drive.google.com/uc?id={PDF_LINKS[pdf_key]}'
                try:
                    gdown.download(url, pdf_file_path, quiet=False)
                except Exception as e:
                    st.error(f"❌ 구글 드라이브에서 파일을 가져오지 못했습니다: {e}")
                    return None
        else:
            st.error(f"⚠️ '{pdf_key}'의 구글 드라이브 ID가 등록되지 않았습니다. 코드 상단의 PDF_LINKS 설정을 확인하세요.")
            return None
    return pdf_file_path

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: 
            return json.load(f)
    return {} if "progress" in file_path else []

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_correct(user_ans, correct_ans):
    if not user_ans: 
        return False
    
    def clean(s):
        s = str(s).strip().lower()
        for char in [".", "?", "!", ",", "°", " "]:
            s = s.replace(char, "")
        return s
        
    u_list = [clean(x) for x in str(user_ans).split("|") if clean(x)]
    c_list = [clean(x) for x in str(correct_ans).split("|") if clean(x)]
    
    if len(u_list) != len(c_list): 
        return False
    return sorted(u_list) == sorted(c_list)

def reset_feedback():
    if 'show_results' in st.session_state: 
        st.session_state['show_results'] = False
    if 'show_score_board' in st.session_state: 
        st.session_state['show_score_board'] = False

def extract_cropped_page(pdf_path, page_num, crop_range, q_id):
    if not os.path.exists(pdf_path): 
        return None
    doc = fitz.open(pdf_path)
    if page_num >= len(doc): 
        return None
    page = doc[page_num]
    
    zoom = 3.0
    mat = fitz.Matrix(zoom, zoom)
    top_pct, bottom_pct, left_pct, right_pct = crop_range[0], crop_range[1], crop_range[2], crop_range[3]
    
    rect = page.rect
    crop_rect = fitz.Rect(
        rect.x0 + (rect.width * (left_pct / 100.0)), 
        rect.y0 + (rect.height * (top_pct / 100.0)), 
        rect.x0 + (rect.width * (right_pct / 100.0)), 
        rect.y0 + (rect.height * (bottom_pct / 100.0))
    )
    
    pix = page.get_pixmap(matrix=mat, clip=crop_rect)
    return pix.tobytes("png")

def get_full_page_image(pdf_path, page_num):
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img_data = pix.tobytes("png")
    return Image.open(io.BytesIO(img_data))

if 'combo' not in st.session_state: 
    st.session_state['combo'] = 0
if 'wrong_list' not in st.session_state: 
    st.session_state['wrong_list'] = []

st.set_page_config(page_title="지역아동센터 학습관리", layout="centered")
menu = st.sidebar.selectbox("메뉴 선택", ["✍️ 학생 문제 풀기", "🛠️ [선생님 전용] 그림 자르기 조절기", "🔒 관리자 대시보드"])

if menu == "✍️ 학생 문제 풀기":
    st.title("🏫 지역아동센터 온라인 교실")
    
    if st.session_state['combo'] > 0:
        st.markdown(f"<div style='text-align: right; color: #ff9800; font-weight: bold; font-size: 20px;'>🔥 현재 {st.session_state['combo']} 콤보 달성 중!</div>", unsafe_allow_html=True)
    
    student_name = st.text_input("너의 이름을 입력해줘", "").strip()
    
    if student_name:
        st.success(f"🎒 확인 완료! {student_name} 어린이, 오늘도 화이팅!")
        
        if st.session_state.get('show_score_board') and st.session_state.get('last_score_name') == student_name:
            score_text = st.session_state['last_score_val']
            is_perfect = "100점" in score_text
            bg_color = "#f0f7f4" if is_perfect else "#fff3f3"
            border_color = "#2e7d32" if is_perfect else "#d32f2f"
            title_text = "🏆 만점 성공! 진도 저장 완료!" if is_perfect else "📝 채점 결과 확인 (오답 고치기)"
            
            score_display = f"<h2 style='color: {border_color}; margin-top:12px; margin-bottom:0; font-weight: bold;'>시험 점수: {score_text}</h2>"
            if not is_perfect:
                score_display += "<p style='color: #d32f2f; margin-top:5px; font-size:14px; font-weight:bold;'>⚠️ 틀린 문제(❌)가 있습니다! 정답을 고친 뒤 선생님께 재제출하세요.</p>"
            
            st.markdown(f"""
            <div style='background-color: {bg_color}; padding: 20px; border-radius: 10px; border-left: 5px solid {border_color}; margin-top: 15px; margin-bottom: 25px;'>
                <h3 style='margin-top:0; color: {border_color};'>{title_text}</h3>
                <p style='margin-bottom:5px; font-size: 15px;'><b>이름:</b> {st.session_state['last_score_name']}</p>
                <p style='margin-bottom:5px; font-size: 15px;'><b>풀이 범위:</b> {st.session_state['last_score_range']}</p>
                {score_display}
            </div>
            """, unsafe_allow_html=True)
            
            if not is_perfect and st.session_state['wrong_list']:
                with st.expander("📚 내가 틀린 문제 (오답 노트) 확인하기", expanded=True):
                    wrong_text_content = f"--- {student_name} 어린이의 오답 노트 ---\n\n"
                    for w_idx, wq in enumerate(st.session_state['wrong_list']):
                        st.markdown(f"**[{w_idx+1}] {wq['question']}**")
                        st.markdown(f"👉 정답: `{wq['answer']}`")
                        st.markdown("---")
                        wrong_text_content += f"문제: {wq['question']}\n정답: {wq['answer']}\n\n"
                    
                    st.download_button(
                        label="📥 오답 노트 다운로드 (메모장 파일)",
                        data=wrong_text_content.encode('utf-8'),
                        file_name=f"{student_name}_오답노트.txt",
                        mime="text/plain"
                    )
            
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        with col1: selected_grade = st.selectbox("학년 선택", [1, 2, 3, 4, 5, 6], index=3)
        with col2: selected_semester = st.selectbox("학기 선택", [1, 2], index=0)
        with col3: selected_subject = st.selectbox("과목 선택", ["국어", "수학", "사회", "과학", "영어"], index=1)
            
        subject_key = f"{selected_grade}_{selected_semester}_{selected_subject}"
        question_filename = os.path.join(QUESTION_DIR, f"{subject_key}.json")
        
        if st.button("📝 내 진도 불러오기", type="primary"):
            questions = load_data(question_filename)
            if not questions:
                st.error(f"⚠️ 아직 {selected_grade}학년 {selected_semester}학기 {selected_subject} 문제가 준비되지 않았습니다.")
            else:
                progress_data = load_data(PROGRESS_FILE)
                if not isinstance(progress_data, dict): progress_data = {}
                student_progress = progress_data.get(student_name, {})
                if not isinstance(student_progress, dict): student_progress = {}
                
                last_solved = student_progress.get(subject_key, 0)
                remaining_questions = [q for q in questions if q['id'] > last_solved or (q.get('type') == 'concept' and q['id'] >= (last_solved//100)*100)]
                
                if not remaining_questions:
                    st.balloons()
                    st.success("🎉 대단해요! 이 과목의 모든 문제를 다 풀었습니다!")
                else:
                    st.session_state['all_remaining_questions'] = remaining_questions
                    st.session_state['last_solved_id'] = last_solved
                    st.session_state['exam_started'] = True
                    st.session_state['subject_key'] = subject_key
                    st.session_state['show_results'] = False  
                    st.session_state['show_score_board'] = False
                    st.session_state['wrong_list'] = []

        if st.session_state.get('exam_started'):
            pdf_key = f"{selected_grade}_{selected_semester}_{selected_subject}"
            pdf_file_path = download_pdf_from_drive(pdf_key)
            
            if pdf_file_path and os.path.exists(pdf_file_path):
                all_remaining = st.session_state['all_remaining_questions']
                available_pages = sorted(list(set([q['page'] for q in all_remaining])))
                
                if not available_pages:
                    st.success("모든 페이지를 다 풀었습니다!")
                else:
                    st.info(f"📍 어제까지 {st.session_state['last_solved_id'] % 100}번 문제 완료! 오늘 공부할 페이지를 선택하세요.")
                    
                    selected_page = st.selectbox(
                        "📖 오늘 풀이할 페이지 번호", 
                        options=available_pages, 
                        format_func=lambda x: f"PDF {x}쪽 모아보기"
                    )
                    st.markdown("---")
                    
                    page_questions = [q for q in all_remaining if q['page'] == selected_page]
                    concept_qs = [q for q in page_questions if q.get('type') == 'concept']
                    problem_qs = [q for q in page_questions if q.get('type') != 'concept']

                    if concept_qs:
                        with st.expander(f"💡 {selected_page}쪽 문제 풀다가 헷갈리면 여기를 누르세요! [핵심 개념]", expanded=False):
                            for cq in concept_qs:
                                c_img_data = extract_cropped_page(pdf_file_path, cq["page"], cq.get("crop", [0,100,0,100]), cq["id"])
                                if c_img_data: 
                                    st.image(c_img_data, caption=cq.get('question', "핵심 개념 설명"))
                        st.markdown("---")

                    current_answered_ids = []
                    for q in problem_qs:
                        skipped = st.session_state.get(f"skip_{q['id']}", False)
                        num_a = q.get('num_ans', 1)
                        answered = False
                        for i in range(num_a):
                            if st.session_state.get(f"q_{q['id']}_{i}"):
                                answered = True
                        if answered or skipped:
                            current_answered_ids.append(q['id'])
                            
                    dyn_max_answered_id = max(current_answered_ids) if current_answered_ids else None
                    
                    user_answers = {}
                    for q in problem_qs:
                        st.subheader(f"Q. {q['question']}")
                        
                        if "page" in q:
                            crop_range = q.get("crop", [0, 100, 0, 100])
                            img_data = extract_cropped_page(pdf_file_path, q["page"], crop_range, q["id"])
                            if img_data: 
                                st.image(img_data)
                        
                        if q.get('type') == 'blank':
                            num_ans = q.get('num_ans', 1)
                            cols = st.columns(num_ans)
                            ans_parts = []
                            for i in range(num_ans):
                                with cols[i]:
                                    ans_val = st.text_input(f"답 {i+1}:", key=f"q_{q['id']}_{i}", on_change=reset_feedback).strip()
                                    ans_parts.append(ans_val)
                            user_answers[q['id']] = "|".join(ans_parts)
                        else:
                            user_answers[q['id']] = st.radio("보기 선택:", q.get('options', []), key=f"q_{q['id']}", index=None, on_change=reset_feedback)
                        
                        st.checkbox("⏭️ 컴퓨터로 풀기 어려운 문제 건너뛰기 (선생님 허락 필요)", key=f"skip_{q['id']}", on_change=reset_feedback)
                        
                        if st.session_state.get('show_results') and dyn_max_answered_id and q['id'] <= dyn_max_answered_id:
                            if st.session_state.get(f"skip_{q['id']}"):
                                st.warning("⏭️ 선생님 권한으로 건너뛰었습니다. (정답 처리됨)")
                            else:
                                ans = user_answers.get(q['id'])
                                if is_correct(ans, q.get('answer', '')):
                                    st.success("⭕ 정답입니다!")
                                elif not ans.replace("|", "").strip():
                                    st.error("❌ 문제를 풀지 않았습니다! 정답을 입력해 주세요.")
                                else:
                                    st.error(f"❌ 틀렸습니다! 다시 한 번 생각해 보세요.")
                        st.markdown("---")
                    
                    st.markdown(f"### 🔒 {selected_page}쪽 분량 제출 (선생님 확인 필요)")
                    teacher_pwd = st.text_input("선생님 비밀번호를 입력해줘:", type="password", key="student_submit_pwd")
                    
                    if st.button("💾 이 페이지 제출 및 진도 저장하기", type="primary"):
                        if teacher_pwd == "0094":
                            answered_ids = [q['id'] for q in problem_qs if user_answers.get(q['id'], "").replace("|", "").strip() or st.session_state.get(f"skip_{q['id']}")]
                            
                            if not answered_ids:
                                st.warning("⚠️ 풀이한 문제가 없습니다! 문제를 풀고 채점을 요청하세요.")
                            else:
                                max_ans_id = max(answered_ids)
                                total_problems = [q for q in problem_qs if q['id'] <= max_ans_id]
                                correct_count = 0
                                has_error = False
                                valid_problem_count = 0
                                
                                st.session_state['wrong_list'] = [] 
                                
                                for q in total_problems:
                                    if st.session_state.get(f"skip_{q['id']}"):
                                        continue
                                        
                                    valid_problem_count += 1
                                    ans = user_answers.get(q['id'])
                                    if is_correct(ans, q.get('answer', '')): 
                                        correct_count += 1
                                        st.session_state['combo'] += 1
                                    else: 
                                        has_error = True
                                        st.session_state['combo'] = 0
                                        st.session_state['wrong_list'].append(q)
                                
                                score = int((correct_count / valid_problem_count) * 100) if valid_problem_count > 0 else 100
                                
                                # 🌟 대시보드 줄맞춤 및 학습 페이지 추가 완료 구역
                                logs = load_data(LOG_FILE)
                                if not isinstance(logs, list): 
                                    logs = []
                                logs.append({
                                    "날짜": datetime.now().strftime("%Y-%m-%d"),
                                    "시간": datetime.now().strftime("%H:%M"),
                                    "이름": student_name,
                                    "과목": f"{selected_grade}학년 {selected_semester}학기 {selected_subject}",
                                    "학습 페이지": f"{selected_page}쪽",
                                    "점수": f"{score}점"
                                })
                                save_data(LOG_FILE, logs)
                                
                                st.session_state['last_score_name'] = student_name
                                st.session_state['last_score_subject'] = selected_subject
                                st.session_state['last_score_range'] = f"{selected_grade}학년 {selected_semester}학기 PDF {selected_page}쪽 완료"
                                st.session_state['last_score_val'] = f"{score}점"
                                st.session_state['show_score_board'] = True
                                st.session_state['show_results'] = True
                                
                                if has_error:
                                    st.error(f"❌ 제출 완료! 그러나 틀린 문제가 있어 진도는 저장되지 않았습니다. ({score}점)")
                                    st.rerun()
                                else:
                                    progress_data = load_data(PROGRESS_FILE)
                                    if not isinstance(progress_data, dict): 
                                        progress_data = {}
                                    if student_name not in progress_data: 
                                        progress_data[student_name] = {}
                                    
                                    current_max = progress_data[student_name].get(st.session_state['subject_key'], 0)
                                    progress_data[student_name][st.session_state['subject_key']] = max(current_max, max_ans_id)
                                    save_data(PROGRESS_FILE, progress_data)
                                    
                                    st.balloons()
                                    st.session_state['exam_started'] = False
                                    st.session_state['show_results'] = False
                                    st.rerun()
                        else:
                            st.error("❌ 비밀번호가 올바르지 않습니다.")

elif menu == "🛠️ [선생님 전용] 그림 자르기 조절기":
    st.title("✂️ 문제집 자르기 도구")
    work_mode = st.radio("어떤 방식으로 자르시겠습니까?", ["🎛️ 슬라이더 조절 (기존 안전모드)", "🖱️ 그림판 마우스 드래그 모드"])
    
    edit_col1, edit_col2, edit_col3 = st.columns(3)
    with edit_col1: test_grade = st.selectbox("학년", [1, 2, 3, 4, 5, 6], index=3)
    with edit_col2: test_semester = st.selectbox("학기", [1, 2], index=0)
    with edit_col3: test_subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어"], index=1)
        
    test_pdf_key = f"{test_grade}_{test_semester}_{test_subject}"
    pdf_file_path = download_pdf_from_drive(test_pdf_key)
    
    if not pdf_file_path or not os.path.exists(pdf_file_path): 
        st.error(f"⚠️ 구글 드라이브 ID 사전에 '{test_pdf_key}' 정보가 등록되지 않았거나 다운로드에 실패했습니다.")
    else:
        doc = fitz.open(pdf_file_path)
        total_pages = len(doc)
        test_page = st.number_input(f"현재 켜져있는 PDF 페이지 번호 (총 {total_pages}페이지)", min_value=0, max_value=total_pages-1, value=0)
        
        question_filename = os.path.join(QUESTION_DIR, f"{test_pdf_key}.json")
        questions_list = load_data(question_filename)
        if not isinstance(questions_list, list): 
            questions_list = []
        
        saved_ids = [q['id'] for q in questions_list if q['id'] != 0]
        if saved_ids:
            st.info(f"💡 현재 과목 저장된 가장 마지막 번호(ID): {max(saved_ids)}")
        else:
            st.info("💡 아직 저장된 문제가 없습니다.")

        st.markdown("### 🎛️ 1. 문제 정보 설정 (외울 필요 0%)")
        col_type, col_num = st.columns(2)
        with col_type:
            q_type_kor = st.radio("이 영역은 무엇인가요?", ["📝 일반 문제", "💡 핵심 개념칸"])
        with col_num:
            if q_type_kor == "📝 일반 문제":
                q_num_on_page = st.number_input("이 페이지의 몇 번 문제인가요?", min_value=1, max_value=50, value=1)
            else:
                q_num_on_page = 0
                st.info("개념칸은 문제 번호가 필요 없습니다.")
                
        target_id = (test_page * 100) + q_num_on_page
        target_type = "concept" if q_type_kor == "💡 핵심 개념칸" else "blank"
        
        existing_q = next((q for q in questions_list if q['id'] == target_id), None)
        
        if q_type_kor == "💡 핵심 개념칸":
            default_title = existing_q['question'] if existing_q else f"{test_page}쪽 핵심 개념"
        else:
            default_title = existing_q['question'] if existing_q else f"{test_page}쪽 {q_num_on_page}번"
            
        default_ans = existing_q.get('answer', '') if existing_q else ""
        
        st.markdown("### 🏷️ 2. 정답 및 표시될 이름 입력")
        custom_title = st.text_input("📚 학생 화면에 보여질 이름", value=default_title)
        
        if target_type != "concept":
            st.markdown("---")
            num_ans = st.number_input("정답 칸 개수 (학생에게 보여줄 빈칸 수)", min_value=1, max_value=4, value=existing_q.get('num_ans', 1) if existing_q else 1)
            
            ans_cols = st.columns(num_ans)
            custom_answers_list = []
            exist_ans_parts = default_ans.split("|") if default_ans else []
            
            for i in range(num_ans):
                with ans_cols[i]:
                    def_val = exist_ans_parts[i] if i < len(exist_ans_parts) else ""
                    custom_answers_list.append(st.text_input(f"🔑 정답 {i+1}", value=def_val))
                    
            custom_answer = "|".join(custom_answers_list)
        else:
            num_ans = 1
            custom_answer = ""
                
        st.markdown("---")
        
        if work_mode == "🖱️ 그림판 마우스 드래그 모드":
            if not HAS_CROPPER: 
                st.error("도구가 설치되지 않았습니다.")
            else:
                img = get_full_page_image(pdf_file_path, test_page)
                cropped_img, box = st_cropper(img, realtime_update=True, box_color='#FF0000', return_type='both')
                w, h = img.size
                top_p, bottom_p = int((box['top'] / h) * 100), int(((box['top'] + box['height']) / h) * 100)
                left_p, right_p = int((box['left'] / w) * 100), int(((box['left'] + box['width']) / w) * 100)
                final_crop = [top_p, bottom_p, left_p, right_p]
                st.image(cropped_img, caption="결과물 미리보기")
                
                if st.button(f"💾 마우스 영역과 정보를 저장하기", type="primary"):
                    found = False
                    for q in questions_list:
                        if q['id'] == target_id:
                            q['page'], q['crop'], q['type'] = test_page, final_crop, target_type
                            q['question'] = custom_title
                            q['answer'] = custom_answer
                            q['num_ans'] = num_ans
                            found = True
                            break
                    if not found:
                        questions_list.append({
                            "id": target_id, "type": target_type, "question": custom_title, 
                            "page": test_page, "crop": final_crop, "answer": custom_answer, 
                            "num_ans": num_ans, "options": []
                        })
                        questions_list = sorted(questions_list, key=lambda x: x['id'])
                    save_data(question_filename, questions_list)
                    st.success(f"🎉 성공! 문제 정보가 완벽하게 저장되었습니다!")
        else:
            col_y, col_x = st.columns(2)
            with col_y: 
                live_top = st.number_input("위쪽 자르기", value=5)
                live_bottom = st.number_input("아래쪽 자르기", value=35)
            with col_x: 
                live_left = st.number_input("왼쪽 자르기", value=0)
                live_right = st.number_input("오른쪽 자르기", value=50)
            final_crop = [live_top, live_bottom, live_left, live_right]
            
            if st.button(f"💾 슬라이더 수치와 정보를 저장하기", type="primary"):
                found = False
                for q in questions_list:
                    if q['id'] == target_id:
                        q['page'], q['crop'], q['type'] = test_page, final_crop, target_type
                        q['question'] = custom_title
                        q['answer'] = custom_answer
                        q['num_ans'] = num_ans
                        found = True
                        break
                if not found:
                    questions_list.append({
                        "id": target_id, "type": target_type, "question": custom_title, 
                        "page": test_page, "crop": final_crop, "answer": custom_answer, 
                        "num_ans": num_ans, "options": []
                    })
                    questions_list = sorted(questions_list, key=lambda x: x['id'])
                save_data(question_filename, questions_list)
                st.success(f"🎉 성공! 문제 정보가 완벽하게 저장되었습니다!")
            
            img_data = extract_cropped_page(pdf_file_path, test_page, final_crop, "test_live")
            if img_data: 
                st.image(img_data)

elif menu == "🔒 관리자 대시보드":
    st.title("🔒 센터 관리자 대시보드")
    if st.text_input("비밀번호:", type="password") == "0094":
        st.markdown("### 🏆 전체 아동 종합 점수판")
        logs = load_data(LOG_FILE)
        if isinstance(logs, list) and len(logs) > 0: 
            st.dataframe(logs[::-1], use_container_width=True)
        else: 
            st.info("ℹ️ 기록이 없습니다.")
        
        st.markdown("---")
        st.subheader("📋 아동별 최종 현재 진도 현황")
        progress = load_data(PROGRESS_FILE)
        if isinstance(progress, dict): 
            st.json(progress)
