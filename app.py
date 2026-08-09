import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import email.utils
from google import genai
import re, time, hmac, hashlib, base64

# ====================================================
# 🔒 1단계: 웹사이트 접속용 비밀번호 자물쇠 만들기
# ====================================================
def check_password():
    """비밀번호가 맞아야만 아래 본문을 보여주는 함수입니다."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔐 나만의 키워드 툴 (접근 제한)")
        st.text_input("비밀번호를 입력하세요:", type="password", key="password")
        
        # 사용자가 비밀번호를 입력하면, 서버 비밀 금고(APP_PASSWORD)와 비교합니다.
        if st.session_state.password == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun() # 화면 새로고침
        elif st.session_state.password != "":
            st.error("비밀번호가 틀렸습니다. 다시 확인해주세요.")
        return False
    return True

# 통과하지 못하면 여기서 프로그램 실행을 멈춥니다. (본문 노출 안 됨)
if not check_password():
    st.stop()


# ====================================================
# 🛡️ 2단계: API 키 안전하게 숨기기 (비밀 금고 연동)
# ====================================================
GEMINI_KEY = st.secrets["GEMINI_KEY"]
AD_ID = st.secrets["AD_ID"]
AD_LICENSE = st.secrets["AD_LICENSE"]
AD_SECRET = st.secrets["AD_SECRET"]
NAVER_ID = st.secrets["NAVER_ID"]
NAVER_SECRET = st.secrets["NAVER_SECRET"]


# ====================================================
# 💎 3단계: 진짜 프로그램 본문 (우리가 만든 완벽한 코드)
# ====================================================
def get_naver_signature(timestamp, method, path, secret):
    msg = timestamp + "." + method + "." + path
    return base64.b64encode(hmac.new(secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()).decode()

def parse_cnt(val):
    s = str(val).strip()
    if not s or s == '-' or '<' in s: return 5
    try: return int(s.replace(',', ''))
    except: return 0

def get_blog_count (kw):
    # 네이버 클라우드 플랫폼(NAVER API HUB) 전용 헤더로 변경
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_ID,
        "X-NCP-APIGW-API-KEY": NAVER_SECRET
    }
    try:
        # 네이버 클라우드 플랫폼 전용 주소(URL)로 변경
        res = requests.get("https://naverapihub.apigw.ntruss.com/search/v1/blog", headers=headers, params={"query": kw, "display": 1}, timeout=5)
        return res.json().get('total', 0) if res.status_code == 200 else 0
    except: return 0

def fetch_naver_autocompletions(keyword):
    url = "https://ac.search.naver.com/nx/ac"
    params = {"q": keyword, "con": 1, "frm": "nv", "ans": 2, "r_format": "json", "r_enc": "UTF-8", "r_unicode": 0, "t_kwnm": 2, "st": 100, "r_group": 1}
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            return [item[0] for item in res.json().get('items', [[]])[0]]
    except: pass
    return []

st.set_page_config(page_title="나만의 키워드 마스터", layout="wide")
st.title("🚀 나만의 블로그 키워드 올인원 툴")

tab1, tab2 = st.tabs(["📝 1. 타 블로그 벤치마킹 분석", "💎 2. 황금 롱테일 키워드 전수조사"])

with tab1:
    st.subheader("최신 50개 포스팅 타겟 키워드 분석")
    blog_id = st.text_input("벤치마킹할 네이버 블로그 아이디를 입력하세요:", key="blog_id")
    
    if st.button("분석 시작", type="primary", key="btn_tab1"):
        if not blog_id:
            st.warning("아이디를 입력해주세요.")
        else:
            with st.spinner('제미나이 AI가 글의 문맥을 읽고 분석 중입니다...'):
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    url = f"https://rss.blog.naver.com/{blog_id}.xml"
                    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    soup = BeautifulSoup(response.content, 'xml')
                    items = soup.find_all('item')[:50]
                    
                    titles = [item.find('title').text.strip() for item in items]
                    pub_dates = [email.utils.parsedate_to_datetime(item.find('pubDate').text).strftime("%Y-%m-%d") for item in items]
                    
                    prompt = "당신은 네이버 블로그 SEO 전문가입니다. 다음 50개의 블로그 제목에서 사람들이 검색할 법한 '메인 키워드(명사 1~2개 조합)'를 하나씩만 뽑아주세요.\n반드시 '번호. 키워드' 형식으로 대답하세요.\n\n[제목 목록]\n"
                    for i, t in enumerate(titles): prompt += f"{i+1}. {t}\n"
                    
                    ai_response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
                    
                    keyword_dict = {}
                    for line in ai_response.text.split('\n'):
                        match = re.match(r'^(\d+)\.\s*(.+)$', line.strip())
                        if match: keyword_dict[int(match.group(1)) - 1] = match.group(2).strip()

                    data = []
                    my_bar = st.progress(0, text="네이버 광고 API에서 연관 키워드를 추출하는 중입니다...")
                    for i in range(len(titles)):
                        main_kw = keyword_dict.get(i, "키워드 없음")
                        rel_kws = "조회 불가"
                        if main_kw and main_kw not in ["추출 실패", "키워드 없음"]:
                            time.sleep(0.3)
                            timestamp = str(int(time.time() * 1000))
                            headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_LICENSE, "X-Customer": str(AD_ID), "X-Signature": get_naver_signature(timestamp, "GET", "/keywordstool", AD_SECRET)}
                            try:
                                res = requests.get("https://api.naver.com/keywordstool", headers=headers, params={"hintKeywords": main_kw.replace(" ", ""), "showDetail": "1"})
                                if res.status_code == 200:
                                    kw_list = res.json().get('keywordList', [])
                                    top_kws = [k['relKeyword'] for k in kw_list if k['relKeyword'] != main_kw.replace(" ", "")]
                                    rel_kws = ", ".join(top_kws[:5]) if top_kws else "연관 키워드 없음"
                            except: pass
                        
                        data.append({"발행 날짜": pub_dates[i], "제목": titles[i], "메인 키워드": main_kw, "연관 추천 키워드": rel_kws})
                        my_bar.progress((i + 1) / len(titles), text=f"({i+1}/{len(titles)}) 데이터 수집 중...")
                        
                    my_bar.empty()
                    df_result1 = pd.DataFrame(data)
                    st.success("✅ 분석 완료!")
                    st.dataframe(df_result1, use_container_width=True)
                    
                    csv = df_result1.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(label="📥 CSV 파일로 다운로드", data=csv, file_name=f"{blog_id}_벤치마킹분석.csv", mime="text/csv")
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")

with tab2:
    st.subheader("씨앗 키워드 기반 연관/롱테일 키워드 전수조사")
    target_kw = st.text_input("씨앗 키워드를 입력하세요 (예: 삼성전자 주가):", key="target_kw")
    
    if st.button("전수 조사 시작 (타이머 장착 버전)", type="primary", key="btn_tab2"):
        if not target_kw:
            st.warning("키워드를 입력해주세요.")
        else:
            CONSONANTS = ['ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅎ', 'ㅍ', 'ㄲ', 'ㄸ', 'ㅃ', 'ㅆ', 'ㅉ']
            NUMBERS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
            ALPHABETS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
            EXT_SUFFIXES = CONSONANTS + NUMBERS + ALPHABETS
            
            status_text = st.empty()
            status_text.info("⚡ 1단계: 네이버 광고 API 연동 및 연관 키워드 싹쓸이 중입니다...")
            
            raw_keywords = set()
            mandatory_terms = [t.lower() for t in target_kw.split()]
            
            ad_seeds = []
            api_query = target_kw.replace(" ", "")
            timestamp = str(int(time.time() * 1000))
            headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_LICENSE, "X-Customer": str(AD_ID), "X-Signature": get_naver_signature(timestamp, "GET", "/keywordstool", AD_SECRET)}
            try:
                res = requests.get("https://api.naver.com/keywordstool", headers=headers, params={"hintKeywords": api_query, "showDetail": "1"})
                if res.status_code == 200:
                    for k in res.json().get('keywordList', []):
                        rel_kw_clean = k['relKeyword'].replace(" ", "").lower()
                        if all(term in rel_kw_clean for term in mandatory_terms):
                            ad_seeds.append(k['relKeyword'])
            except:
                pass
            
            basic_seeds = fetch_naver_autocompletions(target_kw)
            seeds_to_explore = list(set([target_kw] + basic_seeds + ad_seeds))
            
            total_combinations = len(seeds_to_explore) * len(EXT_SUFFIXES)
            progress_gather = st.progress(0, text="자음/숫자/알파벳 조합 2차 심층 수집 중...")
            
            current_step = 0
            for seed in seeds_to_explore:
                seed_clean = seed.replace(" ", "").lower()
                if all(term in seed_clean for term in mandatory_terms):
                    raw_keywords.add(seed.replace(" ", ""))
                    
                for suffix in EXT_SUFFIXES:
                    search_term = f"{seed} {suffix}"
                    for kw in fetch_naver_autocompletions(search_term):
                        kw_clean = kw.replace(" ", "").lower()
                        if all(term in kw_clean for term in mandatory_terms):
                            raw_keywords.add(kw.replace(" ", ""))
                            
                    current_step += 1
                    progress_gather.progress(current_step / total_combinations, text=f"2차 심층 수집 진행률 ({current_step}/{total_combinations})")
                    time.sleep(0.05)
                    
            progress_gather.empty()
            target_list = list(raw_keywords)
            total_targets = len(target_list)
            
            if total_targets == 0:
                st.warning("수집된 연관 키워드가 없습니다.")
            else:
                status_text.info("🔍 2단계: 수집된 황금 키워드 후보들의 조회수와 문서 수를 분석합니다.")
                
                col1, col2, col3 = st.columns(3)
                metric_total = col1.empty()
                metric_current = col2.empty()
                metric_found = col3.empty()
                
                metric_total.metric("전체 탐색 목표 (수집된 단어)", f"{total_targets} 개")
                metric_current.metric("현재 분석 완료", "0 개")
                metric_found.metric("발견된 유효 키워드", "0 개")
                
                current_status = st.empty()
                progress_analyze = st.progress(0, text="조회수 분석 준비 중...")
                table_container = st.empty()
                
                global_results = []
                found_count = 0
                start_time = time.time()
                
                for idx, kw in enumerate(target_list):
                    current_status.markdown(f"### 📡 **지금 찌르는 중:** `{kw}`")
                    metric_current.metric("현재 분석 완료", f"{idx + 1} 개")
                    
                    elapsed_time = time.time() - start_time
                    avg_time_per_item = elapsed_time / (idx + 1) if idx > 0 else 0.4 
                    remaining_items = total_targets - (idx + 1)
                    eta_seconds = int(remaining_items * avg_time_per_item)
                    
                    m, s = divmod(eta_seconds, 60)
                    eta_str = f"{m}분 {s}초" if m > 0 else f"{s}초"
                    
                    progress_analyze.progress((idx + 1) / total_targets, text=f"API 정밀 분석 중 ({(idx+1)}/{total_targets})  |  ⏳ 남은 시간: 약 {eta_str}")
                    
                    pc, mo, total = 0, 0, 0
                    timestamp = str(int(time.time() * 1000))
                    ad_headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_LICENSE, "X-Customer": str(AD_ID), "X-Signature": get_naver_signature(timestamp, "GET", "/keywordstool", AD_SECRET)}
                    
                    try:
                        res = requests.get("https://api.naver.com/keywordstool", params={'hintKeywords': kw, 'showDetail': '1'}, headers=ad_headers)
                        if res.status_code == 200 and res.json().get('keywordList'):
                            for item in res.json()['keywordList']:
                                if item['relKeyword'].replace(" ", "").lower() == kw.replace(" ", "").lower():
                                    pc, mo = parse_cnt(item['monthlyPcQcCnt']), parse_cnt(item['monthlyMobileQcCnt'])
                                    total = pc + mo
                                    break
                    except: pass
                    
                    doc_cnt = get_blog_count(kw)
                    
                    if total > 0 or doc_cnt > 0:
                        ratio = round(doc_cnt / total, 2) if total > 0 else 0
                        global_results.append([kw, pc, mo, total, doc_cnt, ratio])
                        found_count += 1
                        metric_found.metric("발견된 유효 키워드", f"{found_count} 개")
                        
                        df_temp = pd.DataFrame(global_results, columns=['키워드', 'PC', 'MO', '조회수합계', '블로그문서수', '경쟁비율']).sort_values(by='조회수합계', ascending=False)
                        table_container.dataframe(df_temp, use_container_width=True)
                        
                    time.sleep(0.3)
                    
                status_text.success(f"✨ 모든 조사가 완료되었습니다! 총 {found_count}개의 진짜 황금 키워드를 발굴했습니다.")
                current_status.empty()
                progress_analyze.empty()
                
                if global_results:
                    final_df = pd.DataFrame(global_results, columns=['키워드', 'PC', 'MO', '조회수합계', '블로그문서수', '경쟁비율']).sort_values(by='조회수합계', ascending=False)
                    csv2 = final_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(label="📥 CSV 파일로 다운로드", data=csv2, file_name=f"{target_kw.replace(' ', '')}_황금키워드리포트.csv", mime="text/csv")