import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from supabase import create_client, Client

# =========================================================
# 🔧 1. 수파베이스(데이터베이스) 연동
# =========================================================
SUPABASE_URL = "https://xuaoetbkjbuokugprssl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh1YW9ldGJramJ1b2t1Z3Byc3NsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODExNjY2MTIsImV4cCI6MjA5Njc0MjYxMn0.83uFvaO297axM7zUvvOR8odg7OuQX5m_kB7vcTz3q0M"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 크롬 브라우저 백그라운드 구동 옵션
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--incognito")

def scrape_entry_projects_with_scroll(url, tag, emoji, max_count):
    """지정된 엔트리 주소에서 '스크롤'을 내려 작품을 대량 수집하는 엔진"""
    print(f"\n🚀 [{tag}] 순수 트렌드 분석 시작 -> {url}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    
    print("   -> ⏳ 페이지 초기 로딩 대기 중 (5초)...")
    time.sleep(5)
    
    # ---------------------------------------------------------
    # 📜 무한 스크롤 엔진 가동 (홍님 요청 사항)
    # ---------------------------------------------------------
    print(f"   -> 📜 스크롤 매크로 가동! 숨겨진 데이터를 끌어올립니다. (목표: {max_count}개)")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # 화면 맨 아래로 강제 스크롤
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2) # 새로운 작품들이 로딩될 때까지 2초 대기
        
        # 현재 화면에 로딩된 작품 개수 확인
        temp_soup = BeautifulSoup(driver.page_source, 'html.parser')
        current_loaded_cards = len(temp_soup.select('a[href^="/project/"]'))
        
        print(f"      ...스크롤 중... 현재 발견된 작품 수: {current_loaded_cards}개")
        
        # 목표치(max_count)를 채웠으면 스크롤 중지
        if current_loaded_cards >= max_count:
            print("      🎯 목표 수량 도달! 스크롤을 멈춥니다.")
            break
            
        # 스크롤을 내렸는데도 화면 길이가 안 늘어나면(끝에 도달하면) 중지
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("      🏁 페이지 끝에 도달하여 스크롤을 멈춥니다.")
            break
        last_height = new_height

    # ---------------------------------------------------------
    # 🕵️‍♂️ 데이터 추출 및 DB 적재 (순수 노가다 작업)
    # ---------------------------------------------------------
    print("   -> 🕵️‍♂️ 데이터 추출 및 DB 전송을 시작합니다...")
    final_soup = BeautifulSoup(driver.page_source, 'html.parser')
    project_links = final_soup.select('a[href^="/project/"]')
    
    collect_count = 0
    collected_urls = set()
    
    for link_tag in project_links:
        if collect_count >= max_count:
            break
            
        href_link = link_tag.get('href', '')
        if len(href_link) < 15 or href_link in collected_urls:
            continue
            
        full_entry_url = "https://playentry.org" + href_link
        collected_urls.add(href_link)
        
        parent_card = link_tag.find_parent('li') or link_tag.find_parent('div')
        if not parent_card:
            continue
            
        title_tag = parent_card.select_one('div[class*="title"]')
        views_tag = parent_card.select_one('div[class*="view"]')
        likes_tag = parent_card.select_one('div[class*="like"]')
        
        if title_tag and views_tag:
            title_text = title_tag.text.strip()
            views_text = views_tag.text.replace(',', '').replace('k', '000').strip()
            likes_text = likes_tag.text.replace(',', '').replace('k', '000').strip() if likes_tag else "0"
            
            try:
                views_int = int(float(views_text))
                likes_int = int(float(likes_text))
            except ValueError:
                views_int = 0
                likes_int = 0

            # 스파이 데이터 저장 (tag 이름표를 달아서 보냄)
            supabase.table("works").insert({
                "username": tag, 
                "work_name": title_text, 
                "entry_url": full_entry_url,
                "views": views_int, 
                "likes": likes_int,
                "topic": "빅데이터분석", 
                "emoji": emoji
            }).execute()
            
            collect_count += 1
            print(f"      ✅ DB 전송 완료 [{collect_count}/{max_count}] : {title_text} (👁️ {views_int})")

    driver.quit()

def clean_old_bigdata():
    """DB 폭발 방지를 위해 URL당 최신 20개(차트용) 기록만 남기고 폐기"""
    print("\n🧹 빅데이터 창고 최적화 (가비지 컬렉션) 시작...")
    try:
        response = supabase.table("works").select("id", "entry_url").in_("username", ["@BIGDATA_TOP", "@BIGDATA_BOTTOM"]).order("id", desc=True).execute()
        url_map = {}
        for row in response.data:
            url = row.get("entry_url")
            if url:
                if url not in url_map: url_map[url] = []
                url_map[url].append(row)

        delete_ids = []
        for url, records in url_map.items():
            if len(records) > 20: # 20개 점(그래프 길이)만 유지
                for old in records[20:]:
                    delete_ids.append(old.get("id"))

        if delete_ids:
            # 100개씩 나눠서 안전하게 서버에서 삭제
            for i in range(0, len(delete_ids), 100):
                batch = delete_ids[i:i+100]
                supabase.table("works").delete().in_("id", batch).execute()
            print(f"   -> 🗑️ 오래된 빅데이터 {len(delete_ids)}개 폐기 완료!")
        else:
            print("   -> ✨ 창고 데이터 용량이 쾌적합니다.")
    except Exception as e:
        print(f"   -> ❌ 데이터 청소 에러: {e}")

if __name__ == "__main__":
    print("=====================================================")
    print("   🏭 TED BigData Factory - 자동 스크롤 파이프라인 가동")
    print("=====================================================")
    
    # 1. 인기 작품 100개 수집 (스선 제외, 순수 인기작)
    scrape_entry_projects_with_scroll(url="https://playentry.org/project/popular", tag="@BIGDATA_TOP", emoji="👑", max_count=100)
    
    # 2. 모든 작품 100개 수집 (신작/비인기작 대조군)
    scrape_entry_projects_with_scroll(url="https://playentry.org/project/all", tag="@BIGDATA_BOTTOM", emoji="🐢", max_count=100)
    
    # 3. 데이터 다이어트
    clean_old_bigdata()
    
    print("\n🏁 모든 빅데이터 200개 수집 및 전송 파이프라인 가동 완료!")
