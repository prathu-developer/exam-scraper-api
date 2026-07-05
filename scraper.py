import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Your exact tracked exams list
TRACKED_EXAMS = [
    "SSC Stenographer 2026",
    "SSC CGL Tier-I 2026",
    "UPSC CAPF AC 2026",
    "IBPS PO Prelims 2026",
    "AFCAT II 2026",
    "CDS II 2026",
    "NDA II 2026",
    "IBPS PO Mains 2026",
    "IBPS Clerk Prelims 2026",
    "SBI PO Prelims 2026",
    "SBI PO Mains 2026"
]

def format_date_string(raw_date):
    """
    Converts a scraped date like 'December 2026' or '15 Dec 2026'
    into the 'YYYY-MM-DD' format required by your SQLite database.
    """
    raw_date = raw_date.strip()
    
    # Try exact day format (e.g., "15 Dec 2026")
    try:
        parsed_date = datetime.strptime(raw_date, "%d %b %Y")
        return parsed_date.strftime("%Y-%m-%d"), True # True = is exact date
    except ValueError:
        pass
        
    # Try Month Year format (e.g., "December 2026")
    try:
        parsed_date = datetime.strptime(raw_date, "%B %Y")
        # If no exact day is given, default to the 1st of the month
        return parsed_date.strftime("%Y-%m-%d"), False # False = not exact date
    except ValueError:
        pass
        
    # Fallback if parsing completely fails (keeps the app from crashing)
    return "2026-12-31", False


def scrape_testbook_calendar():
    print("🌍 Fetching live page from Testbook...")
    url = "https://testbook.com/government-exam-calendar"
    
    # Disguise the script as a normal web browser to avoid blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to load Testbook: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    exam_results = []
    
    print("🔍 Parsing HTML for tracked exams...")
    
    # 1. Find ALL exam names on the page using the exact class
    all_exam_spans = soup.find_all('span', class_='exam-name')
    
    for name_span in all_exam_spans:
        scraped_name = name_span.get_text(strip=True)
        
        # 2. Check if the scraped name matches any of our TRACKED_EXAMS
        # We use a loose match ('in') because Testbook might just say "IBPS PO" 
        # instead of the full "IBPS PO Prelims 2026".
        matched_tracked_name = None
        for tracked in TRACKED_EXAMS:
            # Look for the core name (e.g., "IBPS PO") inside the tracked name
            if scraped_name.lower() in tracked.lower() or tracked.lower() in scraped_name.lower():
                matched_tracked_name = tracked
                break
                
        if matched_tracked_name:
            # 3. Use .find_next() to grab the very next date span in the HTML tree
            # This bridges the gap without needing to know the parent div structure.
            date_span = name_span.find_next('span', class_='help__content help__content--small')
            
            if date_span:
                raw_date_text = date_span.get_text(strip=True)
                
                # 4. Format the date properly for the bot
                formatted_date, is_exact = format_date_string(raw_date_text)
                
                # 5. Build the dictionary object
                exam_obj = {
                    "name": matched_tracked_name,
                    "date": formatted_date,
                    "status": "Expected", # Standard default
                    "is_exact_date": is_exact,
                    "display_date": raw_date_text
                }
                
                # Prevent duplicates (if Testbook lists the same exam twice)
                if not any(e['name'] == matched_tracked_name for e in exam_results):
                    exam_results.append(exam_obj)
                    print(f"✅ Found match: {matched_tracked_name} ➪ {raw_date_text}")

    return exam_results


if __name__ == "__main__":
    latest_data = scrape_testbook_calendar()
    
    if latest_data:
        # Save to JSON file
        with open('exams.json', 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, indent=4)
        print(f"\n🎉 Scraping complete! {len(latest_data)} exams saved to exams.json.")
    else:
        print("\n⚠️ No matching exams found on the page.")
