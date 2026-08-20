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
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔐 나만의 키워드 툴 (접근 제한)")
        st.text_input("비밀번호를 입력하세요:", type="password", key="password")
        
        if st.session_state.password == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun() 
        elif st.session_state.password != "":
            st.error("비밀번호가 틀렸습니다. 다시 확인해주세요.")
        return False
    return True

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
# 💎 3단계: 진짜 프로그램 본문
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
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_ID,
        "X-NCP-APIGW-API-KEY": NAVER_SECRET
    }
    try:
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

# 📌 탭을 5개로 늘립니다.
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 1. 타 블로그 벤치마킹", 
    "💎 2. 롱테일 키워드 전수조사", 
    "⚡ 3. 빠른 일괄 조회", 
    "💡 4. 지식iN 질문 수집기",
    "🔍 5. 연관 키워드 원본 분석"
])

# ====================================================
# 🆕 [기능 변경] 탭 1: 블로그 벤치마킹 (최신글 50개, 방문자수)
# ====================================================
with tab1:
    st.subheader("타겟 블로그 벤치마킹 (최신글 50개, 방문자 수)")
    blog_id = st.text_input("벤치마킹할 네이버 블로그 아이디를 입력하세요:", key="blog_id")
    
    if st.button("분석 시작", type="primary", key="btn_tab1"):
        if not blog_id:
            st.warning("아이디를 입력해주세요.")
        else:
            with st.spinner(f"'{blog_id}' 블로그의 데이터를 스캔하고 있습니다..."):
                try:
                    # ----------------------------------------------------
                    # 1. 방문자 수 (Today / Total) 수집 (안전한 위젯 API 방식)
                    # ----------------------------------------------------
                    today_cnt = "비공개 또는 확인 불가"
                    total_cnt = "위젯에서 확인 불가 시 직접 접속 필요"
                    
                    try:
                        visit_url = f"https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blog_id}"
                        visit_res = requests.get(visit_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                        if visit_res.status_code == 200:
                            v_soup = BeautifulSoup(visit_res.content, 'xml')
                            visitor_data = v_soup.find_all('visitorcnt')
                            if visitor_data:
                                today_cnt = visitor_data[0].get('cnt', today_cnt)
                    except Exception:
                        pass
                    
                    # ----------------------------------------------------
                    # 2. 최신 포스팅 50개 수집 (안전한 RSS 방식)
                    # ----------------------------------------------------
                    recent_posts = []
                    try:
                        rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
                        rss_res = requests.get(rss_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                        rss_soup = BeautifulSoup(rss_res.content, 'xml')
                        items = rss_soup.find_all('item')[:50]
                        
                        for item in items:
                            r_title = item.find('title').text.strip()
                            r_link = item.find('link').text.strip()
                            r_date = email.utils.parsedate_to_datetime(item.find('pubDate').text).strftime("%Y-%m-%d")
                            # 데이터 삽입 순서를 '발행 날짜'가 맨 앞에 오도록 변경했습니다.
                            recent_posts.append({"발행 날짜": r_date, "분류": "최신글", "제목": r_title, "URL": r_link})
                    except Exception:
                         recent_posts = [{"발행 날짜": "-", "분류": "최신글", "제목": "비공개 또는 확인 불가 (RSS 피드 미제공)", "URL": "-"}]
                         
                    # ----------------------------------------------------
                    # 화면 출력 및 데이터 병합
                    # ----------------------------------------------------
                    st.success("✅ 스캔 완료!")
                    
                    col_v1, col_v2 = st.columns(2)
                    col_v1.metric("오늘 방문자 (Today)", f"{today_cnt} 명")
                    col_v2.metric("전체 방문자 (Total)", total_cnt)
                    
                    df_tab1 = pd.DataFrame(recent_posts)
                    
                    st.markdown("### 📊 수집된 최신 글 목록")
                    st.dataframe(
                        df_tab1, 
                        use_container_width=True,
                        column_config={
                            "URL": st.column_config.LinkColumn("링크", display_text="해당 글로 이동")
                        }
                    )
                    
                    # 방문자 수 컬럼 주입 로직을 삭제하여 순수 게시글 데이터만 CSV로 다운로드됩니다.
                    csv_tab1 = df_tab1.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(label="📥 분석 결과 CSV 다운로드", data=csv_tab1, file_name=f"{blog_id}_블로그스캔결과.csv", mime="text/csv")
                    
                except Exception as e:
                    st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")

# ====================================================
# [그대로 유지 + 띄어쓰기 안내 추가] 탭 2: 전수조사
# ====================================================
with tab2:
    st.subheader("씨앗 키워드 기반 연관/롱테일 키워드 전수조사")
    target_kw = st.text_input("씨앗 키워드를 띄어쓰기로 구분해 입력하세요 (예: 삼성전자 주가 -> 두 단어 모두 포함된 키워드만 추출):", key="target_kw")
    
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

# ====================================================
# [그대로 유지] 탭 3: 일괄 조회
# ====================================================
with tab3:
    st.subheader("키워드 검색량 및 블로그 문서 수 일괄 조회")
    st.markdown("💡 단일 키워드를 입력하거나, 여러 개의 키워드를 **줄바꿈(엔터)**으로 구분하여 입력하세요.")
    
    quick_kws_input = st.text_area("조회할 키워드 입력:", height=150, key="quick_kws")
    
    if st.button("빠른 조회 시작", type="primary", key="btn_tab3"):
        if not quick_kws_input.strip():
            st.warning("조회할 키워드를 1개 이상 입력해주세요.")
        else:
            raw_kws = quick_kws_input.split('\n')
            target_kws = [kw.strip() for kw in raw_kws if kw.strip()]
            
            if not target_kws:
                st.warning("유효한 키워드가 없습니다.")
            else:
                quick_results = []
                progress_quick = st.progress(0, text="API 정밀 분석 준비 중...")
                quick_table = st.empty()
                
                for idx, kw in enumerate(target_kws):
                    progress_quick.progress((idx + 1) / len(target_kws), text=f"분석 중: {kw} ({idx+1}/{len(target_kws)})")
                    
                    pc, mo, total = 0, 0, 0
                    timestamp = str(int(time.time() * 1000))
                    ad_headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_LICENSE, "X-Customer": str(AD_ID), "X-Signature": get_naver_signature(timestamp, "GET", "/keywordstool", AD_SECRET)}
                    
                    try:
                        res = requests.get("https://api.naver.com/keywordstool", params={'hintKeywords': kw.replace(" ", ""), 'showDetail': '1'}, headers=ad_headers)
                        if res.status_code == 200 and res.json().get('keywordList'):
                            for item in res.json()['keywordList']:
                                if item['relKeyword'].replace(" ", "").lower() == kw.replace(" ", "").lower():
                                    pc, mo = parse_cnt(item['monthlyPcQcCnt']), parse_cnt(item['monthlyMobileQcCnt'])
                                    total = pc + mo
                                    break
                    except: pass
                    
                    doc_cnt = get_blog_count(kw)
                    
                    ratio = round(doc_cnt / total, 2) if total > 0 else 0
                    quick_results.append([kw, pc, mo, total, doc_cnt, ratio])
                    
                    df_quick = pd.DataFrame(quick_results, columns=['키워드', 'PC', 'MO', '조회수합계', '블로그문서수', '경쟁비율']).sort_values(by='조회수합계', ascending=False)
                    quick_table.dataframe(df_quick, use_container_width=True)
                    
                    time.sleep(0.3)
                    
                progress_quick.empty()
                st.success(f"✨ 총 {len(target_kws)}개 키워드 조회가 깔끔하게 완료되었습니다!")
                
                if quick_results:
                    csv3 = df_quick.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(label="📥 조회 결과 CSV 다운로드", data=csv3, file_name="빠른키워드조회결과.csv", mime="text/csv", key="dl_tab3")


# ====================================================
# 🆕 [신규 추가] 탭 4: 지식iN 질문 수집기
# ====================================================
with tab4:
    st.subheader("💡 지식iN 실제 질문 수집기 (목차/소제목 발굴용)")
    st.markdown("💡 띄어쓰기로 단어를 구분하면, **모든 단어가 포함된 최신 질문(최대 100개)**만 깐깐하게 걸러냅니다.")
    
    kin_kw = st.text_input("수집할 질문의 핵심 키워드를 띄어쓰기로 구분해 입력하세요 (예: 삼성전자 주가):", key="kin_kw")
    
    if st.button("질문 수집 시작 (최신 100개 기준)", type="primary", key="btn_tab4"):
        if not kin_kw.strip():
            st.warning("키워드를 입력해주세요.")
        else:
            with st.spinner("네이버 클라우드 API를 통해 가장 최근에 올라온 지식iN 질문 100개를 분석하고 있습니다..."):
                headers = {
                    "X-NCP-APIGW-API-KEY-ID": NAVER_ID,
                    "X-NCP-APIGW-API-KEY": NAVER_SECRET
                }
                
                # 네이버 서버에는 띄어쓰기를 없애서 일단 100개를 가득 끌어옵니다. (sort="date" 로 최신순 정렬)
                api_query = kin_kw.replace(" ", "")
                params = {"query": api_query, "display": 100, "sort": "date"}
                
                try:
                    res = requests.get("https://naverapihub.apigw.ntruss.com/search/v1/kin", headers=headers, params=params, timeout=10)
                    
                    if res.status_code == 200:
                        items = res.json().get('items', [])
                        
                        if not items:
                            st.warning("수집된 지식iN 질문이 없습니다.")
                        else:
                            # 띄어쓰기를 기준으로 사용자가 입력한 단어들을 리스트로 쪼갭니다 (AND 조건 필터링용)
                            mandatory_terms = [t.lower() for t in kin_kw.split()]
                            kin_results = []
                            
                            for item in items:
                                # 네이버 API가 주는 <b> 같은 불필요한 HTML 태그를 정규식으로 깔끔하게 지워냅니다.
                                raw_title = re.sub(r'<[^>]*>', '', item.get('title', ''))
                                raw_desc = re.sub(r'<[^>]*>', '', item.get('description', ''))
                                link = item.get('link', '')
                                
                                # AND 필터링: 질문 제목에 우리가 원하는 단어들이 모두 포함되어 있는지 깐깐하게 검사
                                if all(term in raw_title.lower() for term in mandatory_terms):
                                    kin_results.append([raw_title, raw_desc, link])
                            
                            if not kin_results:
                                st.warning("최신 100개의 질문 중, 입력하신 단어가 모두 포함된 완벽한 질문이 없습니다.")
                            else:
                                st.success(f"✨ 필터링 완료! 총 {len(kin_results)}개의 유효한 알짜 질문을 발굴했습니다.")
                                
                                df_kin = pd.DataFrame(kin_results, columns=['질문 제목', '내용 미리보기 (Snippet)', '원문 링크'])
                                
                                # 표 출력 (원문 링크를 클릭 가능한 상태로 세팅)
                                st.dataframe(
                                    df_kin, 
                                    use_container_width=True,
                                    column_config={
                                        "원문 링크": st.column_config.LinkColumn("원문 링크", display_text="지식iN 바로가기")
                                    }
                                )
                                
                                # CSV 다운로드 버튼
                                csv4 = df_kin.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                                st.download_button(
                                    label="📥 알짜 질문 리스트 CSV 다운로드", 
                                    data=csv4, 
                                    file_name=f"{kin_kw.replace(' ', '')}_지식iN질문.csv", 
                                    mime="text/csv", 
                                    key="dl_tab4"
                                )
                    else:
                        st.error(f"API 호출 오류 (상태 코드: {res.status_code})")
                except Exception as e:
                    st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")


# ====================================================
# 🆕 [신규 추가] 탭 5: 연관 키워드 원본 분석기
# ====================================================
with tab5:
    st.subheader("🔍 네이버 연관 키워드 원본 싹쓸이 분석")
    st.markdown("💡 네이버 검색광고 API가 제공하는 **모든 연관 키워드(최대 1,000개)**의 검색량과 문서 수를 필터링 없이 그대로 가져옵니다.")
    
    raw_target_kw = st.text_input("분석할 씨앗 키워드를 입력하세요 (예: 정부지원금):", key="raw_target_kw")
    
    if st.button("원본 분석 시작 (최대 1,000개)", type="primary", key="btn_tab5"):
        if not raw_target_kw.strip():
            st.warning("키워드를 입력해주세요.")
        else:
            status_text_5 = st.empty()
            status_text_5.info("📡 1단계: 네이버 광고 API에서 연관 키워드 목록을 가져오는 중입니다...")
            
            # 1. 연관 키워드 목록 수집 (확장 및 필터링 없음)
            api_query = raw_target_kw.replace(" ", "")
            timestamp = str(int(time.time() * 1000))
            headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_LICENSE, "X-Customer": str(AD_ID), "X-Signature": get_naver_signature(timestamp, "GET", "/keywordstool", AD_SECRET)}
            
            raw_keywords_data = []
            try:
                res = requests.get("https://api.naver.com/keywordstool", headers=headers, params={"hintKeywords": api_query, "showDetail": "1"}, timeout=10)
                if res.status_code == 200:
                    keyword_list = res.json().get('keywordList', [])
                    for k in keyword_list:
                        rel_kw = k['relKeyword']
                        pc = parse_cnt(k.get('monthlyPcQcCnt', 0))
                        mo = parse_cnt(k.get('monthlyMobileQcCnt', 0))
                        raw_keywords_data.append({"kw": rel_kw, "pc": pc, "mo": mo, "total": pc + mo})
            except Exception as e:
                st.error(f"광고 API 호출 중 오류가 발생했습니다: {e}")
            
            total_raw_kws = len(raw_keywords_data)
            
            if total_raw_kws == 0:
                st.warning("수집된 연관 키워드가 없습니다.")
            else:
                # 1,000개를 돌리면 시간이 꽤 걸리므로 예상 시간을 보여줍니다.
                status_text_5.info(f"🔍 2단계: 총 {total_raw_kws}개 키워드의 블로그 문서 수를 분석합니다. (예상 소요시간: 약 {int((total_raw_kws*0.3)/60)}분)")
                
                progress_raw = st.progress(0, text="블로그 문서 수 조회 준비 중...")
                table_container_5 = st.empty()
                
                final_raw_results = []
                start_time_5 = time.time()
                
                for idx, item_data in enumerate(raw_keywords_data):
                    kw = item_data["kw"]
                    total_search = item_data["total"]
                    
                    # 실시간 예상 시간 계산
                    elapsed = time.time() - start_time_5
                    avg_time = elapsed / (idx + 1) if idx > 0 else 0.4
                    remaining = total_raw_kws - (idx + 1)
                    eta_sec = int(remaining * avg_time)
                    m, s = divmod(eta_sec, 60)
                    eta_str = f"{m}분 {s}초" if m > 0 else f"{s}초"
                    
                    progress_raw.progress((idx + 1) / total_raw_kws, text=f"문서 수 분석 중: {kw} ({idx+1}/{total_raw_kws}) | 남은 시간: 약 {eta_str}")
                    
                    # 블로그 문서 수 조회
                    doc_cnt = get_blog_count(kw)
                    ratio = round(doc_cnt / total_search, 2) if total_search > 0 else 0
                    
                    final_raw_results.append([kw, item_data["pc"], item_data["mo"], total_search, doc_cnt, ratio])
                    
                    # 브라우저 과부하 방지: 10개마다 한 번씩만 표를 업데이트합니다.
                    if idx % 10 == 0 or idx == total_raw_kws - 1:
                        df_raw = pd.DataFrame(final_raw_results, columns=['키워드', 'PC', 'MO', '조회수합계', '블로그문서수', '경쟁비율']).sort_values(by='조회수합계', ascending=False)
                        table_container_5.dataframe(df_raw, use_container_width=True)
                    
                    time.sleep(0.3)
                    
                progress_raw.empty()
                status_text_5.success(f"✨ 분석 완료! 총 {total_raw_kws}개의 연관 키워드 원본 데이터가 수집되었습니다.")
                
                if final_raw_results:
                    csv5 = df_raw.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label="📥 원본 분석 결과 CSV 다운로드", 
                        data=csv5, 
                        file_name=f"{raw_target_kw.replace(' ', '')}_연관키워드_원본.csv", 
                        mime="text/csv", 
                        key="dl_tab5"
                    )                    