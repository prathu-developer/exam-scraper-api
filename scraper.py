import os
import json
import time
from google import genai
from google.genai import types

# Define the base names of your tracked exams
TRACKED_EXAMS = [
    "SSC Stenographer",
    "SSC CGL Tier-I",
    "UPSC CAPF AC",
    "IBPS PO Prelims",
    "AFCAT II",
    "CDS II",
    "NDA II",
    "IBPS PO Mains",
    "IBPS Clerk Prelims",
    "SBI PO Prelims",
    "SBI PO Mains"
]

def fetch_exam_data_via_search():
    """Loops through each exam, uses Gemini to search the web, and returns a JSON array."""
    
    # Securely fetch the API key from environment variables (or GitHub Secrets)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ CRITICAL: GEMINI_API_KEY environment variable not set.")
        return []

    client = genai.Client(api_key=api_key)
    all_exam_results = []

    print(f"🚀 Starting live internet search for {len(TRACKED_EXAMS)} exams...\n")

    for exam in TRACKED_EXAMS:
        print(f"🔍 Searching the web for: '{exam} exam date 2026'...")
        
        # The prompt is dynamically edited for each exam in the loop
        prompt = f"""
        Search the live internet for the official or most highly expected 2026 exam date for: "{exam} exam date 2026" in India.

        You must return strictly a JSON object. Ensure the object matches this exact schema:
        {{
            "name": "{exam} 2026",
            "date": "The sorting date in YYYY-MM-DD format. If only a tentative month is known, use the 1st day (e.g., '2026-08-01'). If completely unknown, use '2026-12-31'",
            "status": "Strictly use 'Fixed', 'Tentative', or 'Expected' based on the search results",
            "is_exact_date": true (if a specific day or weekend is announced) or false (if only a month/period is known),
            "display_date": "A short, human-readable date (e.g., 'August 2026', '15-20 Aug 2026', or 'To Be Announced')"
        }}
        """

        try:
             # Use gemini-1.5-flash as it is highly optimised for search grounding and JSON output
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1, # Low temperature for factual accuracy
                    response_mime_type="application/json", # Forces standard JSON output
                    tools=[types.Tool(google_search=types.GoogleSearch())] # Grants internet access
                )
            )
            
            # Parse the AI's response directly into a Python dictionary
            result_dict = json.loads(response.text)
            all_exam_results.append(result_dict)
            
            print(f"✅ Found: {result_dict.get('display_date')} (Status: {result_dict.get('status')})\n")
            
            # Crucial: Pause for 4 seconds between requests to avoid hitting free-tier rate limits (429 errors)
            time.sleep(30) 

        except Exception as e:
            print(f"⚠️ Failed to fetch or parse data for {exam}: {e}\n")

    return all_exam_results


if __name__ == "__main__":
    latest_data = fetch_exam_data_via_search()
    
    if latest_data:
        # Save the final array of dictionaries to your JSON file
        with open('exams.json', 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, indent=4)
        print(f"🎉 Search complete! {len(latest_data)} exams successfully saved to exams.json.")
    else:
        print("⚠️ No data was saved. Please check your API key and internet connection.")
