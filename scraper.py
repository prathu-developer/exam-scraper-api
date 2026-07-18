import os
import json
import time
import re
from datetime import datetime
from tavily import TavilyClient

TRACKED_EXAMS = [
    # SSC
    "SSC CGL Tier-I",
    "SSC CGL Tier-II",
    "SSC CHSL Tier-I",
    "SSC CHSL Tier-II",
    "SSC MTS",
    "SSC Selection Post",
    "SSC Stenographer",
    "SSC CPO",

    # Banking
    "IBPS PO Prelims",
    "IBPS PO Mains",
    "IBPS Clerk Prelims",
    "IBPS Clerk Mains",
    "IBPS RRB PO Prelims",
    "IBPS RRB PO Mains",
    "IBPS RRB Office Assistant Prelims",
    "IBPS RRB Office Assistant Mains",
    "SBI PO Prelims",
    "SBI PO Mains",
    "SBI Clerk Prelims",
    "SBI Clerk Mains",

    # RBI
    "RBI Assistant Prelims",
    "RBI Assistant Mains",
    "RBI Grade B Phase-I",
    "RBI Grade B Phase-II",

    # Insurance
    "LIC AAO Prelims",
    "LIC AAO Mains",
    "NIACL AO Prelims",
    "NIACL AO Mains",
    "NICL AO Prelims",
    "NICL AO Mains",
    "UIIC AO Prelims",
    "UIIC AO Mains",
    "GIC Assistant Manager",

    # Regulatory Bodies
    "SEBI Grade A Phase-I",
    "SEBI Grade A Phase-II",
    "NABARD Grade A Prelims",
    "NABARD Grade A Mains",
    "NABARD Grade B Prelims",
    "NABARD Grade B Mains",
    "IRDAI Assistant Manager Phase-I",
    "IRDAI Assistant Manager Phase-II",
    "PFRDA Grade A Phase-I",
    "PFRDA Grade A Phase-II",
    "IFSCA Grade A Phase-I",
    "IFSCA Grade A Phase-II",

    # EPFO & ESIC
    "EPFO EO/AO",
    "ESIC SSO Prelims",
    "ESIC SSO Mains",

    # Intelligence
    "IB ACIO Tier-I",
    "IB ACIO Tier-II",

    # Food Corporation of India
    "FCI Manager",

    # Railways
    "RRB NTPC CBT-1",
    "RRB NTPC CBT-2",

    # Defence
    "CDS-I",
    "CDS-II",
    "AFCAT-I",
    "AFCAT-II",
    "CAPF AC",

    # UPSC
    "UPSC Civil Services Prelims",
    "UPSC Civil Services Mains",
]

def parse_tavily_answer(exam_name, answer_text):
    """
    Extracts dates by locking onto the 'EXAM_DATE:' prefix, ignoring 
    notification/application dates, and parsing ranges like 'July-August'.
    """
    marker_match = re.search(r"EXAM_DATE:\s*(.*)", answer_text, re.IGNORECASE)
    target_text = marker_match.group(1).strip() if marker_match else answer_text

    # THE FIX: Added '?:' to make this a non-capturing group. 
    # This stops Python from duplicating the month and overwriting the year!
    months_regex = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"

    formatted_date = "2026-12-31"
    is_exact = False
    display_date = "To Be Announced"
    status = "Expected"

    # Regex patterns for different date formats
    exact_pattern = r"(\d{1,2})(?:st|nd|rd|th)?\s+(" + months_regex + r")\s+(2026|2027)"
    range_pattern = r"(" + months_regex + r")\s*(?:-|to|and|/|&)\s*(" + months_regex + r")\s+(2026|2027)"
    month_pattern = r"(" + months_regex + r")\s+(2026|2027)"

    try:
        # A. Check for Exact Date (e.g., "15 August 2026")
        if re.search(exact_pattern, target_text, re.IGNORECASE):
            match = re.search(exact_pattern, target_text, re.IGNORECASE)
            day, month, year = match.group(1), match.group(2), match.group(3)
            parsed_date = datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y")
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            display_date = parsed_date.strftime("%d %b %Y")
            is_exact = True

        # B. Check for Month Range (e.g., "July-August 2026")
        elif re.search(range_pattern, target_text, re.IGNORECASE):
            match = re.search(range_pattern, target_text, re.IGNORECASE)
            month1, month2, year = match.group(1), match.group(2), match.group(3)
            parsed_date = datetime.strptime(f"{month1[:3]} {year}", "%b %Y") 
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            display_date = f"{month1.capitalize()}-{month2.capitalize()} {year}"

        # C. Check for Single Month (e.g., "August 2026")
        elif re.search(month_pattern, target_text, re.IGNORECASE):
            match = re.search(month_pattern, target_text, re.IGNORECASE)
            month, year = match.group(1), match.group(2)
            parsed_date = datetime.strptime(f"{month[:3]} {year}", "%b %Y")
            formatted_date = parsed_date.strftime("%Y-%m-%d")
            display_date = parsed_date.strftime("%B %Y")
            
    except Exception as e:
        print(f"⚠️ Regex parsing error on {exam_name}: {e}")

    # Determine status based on wording
    if "official" in target_text.lower() or "announced" in target_text.lower() or "confirmed" in target_text.lower():
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

    print(f"🚀 Starting highly targeted search with Tavily for {len(TRACKED_EXAMS)} exams...\n")

    for exam in TRACKED_EXAMS:
        # THE FIX: Explicit negative constraints and a forced prefix format
        query = (
            f"Find the actual exam or test dates for '{exam} 2026' in India. "
            f"CRITICAL: Ignore notification dates, application deadlines, and admit card dates. I only want the date the test is conducted. "
            f"Respond EXACTLY in this format: 'EXAM_DATE: <DD Month YYYY> or <Month YYYY>'. "
            f"Example: 'EXAM_DATE: July-August 2026' or 'EXAM_DATE: 15 October 2026'."
        )
        
        print(f"🔍 Searching: '{exam}'...")
        
        try:
            response = client.search(query=query, search_depth="advanced", include_answer=True)
            answer = response.get('answer', '')
            
            if not answer:
                print(f"⚠️ No direct answer generated for {exam}. Skipping.")
                continue
                
            print(f"🧠 Tavily Raw Output: {answer}")
            
            result_dict = parse_tavily_answer(exam, answer)
            all_exam_results.append(result_dict)
            
            print(f"✅ Formatted: {result_dict['display_date']} (Status: {result_dict['status']})\n")
            
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
