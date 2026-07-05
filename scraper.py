import os
import json
import time
import re
from datetime import datetime
from tavily import TavilyClient

TRACKED_EXAMS = [
    "SSC Stenographer", "SSC CGL Tier-I", "UPSC CAPF AC", "IBPS PO Prelims",
    "AFCAT II", "CDS II", "NDA II", "IBPS PO Mains", "IBPS Clerk Prelims",
    "SBI PO Prelims", "SBI PO Mains"
]

def parse_tavily_answer(exam_name, answer_text):
    """
    Extracts dates like '15 August 2026' or 'August 2026' from Tavily's text response
    and formats them perfectly for the SQLite database.
    """
    months = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    
    # Regex to hunt for DD Month YYYY and Month YYYY formats
    exact_match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + months + r"\s+(2026|2027)", answer_text, re.IGNORECASE)
    month_match = re.search(months + r"\s+(2026|2027)", answer_text, re.IGNORECASE)
    
    formatted_date = "2026-12-31"
    is_exact = False
    display_date = "To Be Announced"
    status = "Expected"
    
    if exact_match:
        try:
            day = exact_match.group(1)
            month = exact_match.group(2)
            year = exact_match.group(3)
            date_str = f"{day} {month[:3]} {year}"
            parsed_date = datetime.strptime(date_str, "%d %b %Y")
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            display_date = parsed_date.strftime("%d %b %Y")
            is_exact = True
        except ValueError:
            pass
    elif month_match:
        try:
            month = month_match.group(1)
            year = month_match.group(2)
            date_str = f"{month[:3]} {year}"
            parsed_date = datetime.strptime(date_str, "%b %Y")
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            display_date = parsed_date.strftime("%B %Y")
        except ValueError:
            pass
            
    # Determine the status based on Tavily's wording
    if "official" in answer_text.lower() or "announced" in answer_text.lower():
        status = "Fixed" if is_exact else "Tentative"
        
    return {
        "name": f"{exam_name} 2026",
        "date": formatted_date,
        "status": status,
        "is_exact_date": is_exact,
        "display_date": display_date
    }

def fetch_exam_data_with_tavily():
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("❌ CRITICAL: TAVILY_API_KEY environment variable not set.")
        return []

    client = TavilyClient(api_key=api_key)
    all_exam_results = []

    print(f"🚀 Starting live internet search with Tavily for {len(TRACKED_EXAMS)} exams...\n")

    for exam in TRACKED_EXAMS:
        # We instruct Tavily to return a short, direct answer to make parsing easier
        query = f"What is the official or expected exam date for {exam} 2026 in India? Reply with a short sentence containing the month and year."
        print(f"🔍 Searching: '{exam}'...")
        
        try:
            # include_answer=True triggers Tavily's internal AI to summarize the search results
            response = client.search(query=query, search_depth="advanced", include_answer=True)
            answer = response.get('answer', '')
            
            if not answer:
                print(f"⚠️ No direct answer generated for {exam}. Skipping.")
                continue
                
            print(f"🧠 Tavily Answer: {answer}")
            
            result_dict = parse_tavily_answer(exam, answer)
            all_exam_results.append(result_dict)
            
            print(f"✅ Formatted: {result_dict['display_date']} (Status: {result_dict['status']})\n")
            
            # Tavily rate limits are much faster, a 2-second pause is perfectly safe
            time.sleep(2) 

        except Exception as e:
            print(f"⚠️ Failed to fetch data for {exam}: {e}\n")

    return all_exam_results

if __name__ == "__main__":
    latest_data = fetch_exam_data_with_tavily()
    if latest_data:
        with open('exams.json', 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, indent=4)
        print(f"🎉 Search complete! {len(latest_data)} exams saved to exams.json.")
    else:
        print("⚠️ No data was saved. Please check your API key.")
