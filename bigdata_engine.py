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

def scrape_entry_projects(url, tag, emoji, max_count):
    """지정된 엔트리 주소에서 작품을 긁어와 특정 태그로 DB에 저장하는 함수"""
    print(f"\n🚀 [{tag}] 타겟 분석 시작 -> {url}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    
    # 넉넉하게 10초 대기 (엔트리 사이트 로딩 보장)
    print("   -> ⏳ 페이지 로딩 및 데이터 렌더링 대기 중 (10초)...")
    time.sleep(10)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    project_links = soup.select('a[href^="/project/"]')
    
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

            # DB 저장 (tag가 username 역할)
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
            print(f"      ✅ 수집 성공 [{collect_count}/{max_count}] : {title_text} (👁️ {views_int})")

    driver.quit()

def clean_old_bigdata():
    """DB 폭발 방지를 위해 URL당 최신 20개 기록만 남기고 폐기"""
    print("\n🧹 빅데이터 창고 최적화 (가비지 컬렉션) 시작...")
    try:
        # 빅데이터 태그가 붙은 것만 타겟으로 청소
        response = supabase.table("works").select("id", "entry_url").in_("username", ["@BIGDATA_TOP", "@BIGDATA_BOTTOM"]).order("id", desc=True).execute()
        url_map = {}
        for row in response.data:
            url = row.get("entry_url")
            if url:
                if url not in url_map: url_map[url] = []
                url_map[url].append(row)

        delete_ids = []
        for url, records in url_map.items():
            if len(records) > 20:
                for old in records[20:]:
                    delete_ids.append(old.get("id"))

        if delete_ids:
            # 100개씩 나눠서 안전하게 삭제
            for i in range(0, len(delete_ids), 100):
                batch = delete_ids[i:i+100]
                supabase.table("works").delete().in_("id", batch).execute()
            print(f"   -> 🗑️ 오래된 빅데이터 {len(delete_ids)}개 폐기 완료!")
        else:
            print("   -> ✨ 데이터 용량이 쾌적합니다.")
    except Exception as e:
        print(f"   -> ❌ 데이터 청소 에러: {e}")

if __name__ == "__main__":
    print("=====================================================")
    print("   🏭 TED BigData Factory - 데이터 파이프라인 가동")
    print("=====================================================")
    
    # 1. 상위 10개 (대박 작품) -> 인기 게시판 스크래핑
    scrape_entry_projects(url="https://playentry.org/project/popular", tag="@BIGDATA_TOP", emoji="👑", max_count=10)
    
    # 2. 하위 10개 (쪽박/신생 작품) -> 모든 작품(최신순) 게시판 스크래핑
    scrape_entry_projects(url="https://playentry.org/project/all", tag="@BIGDATA_BOTTOM", emoji="🐢", max_count=10)
    
    # 3. 빅데이터 청소부 실행
    clean_old_bigdata()
    
    print("\n🏁 모든 빅데이터 수집 및 전송 파이프라인 가동 완료!")
