import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET
from readability import Document
import os
import time
from google import genai
from google.genai import types

# Load keys safely from GitHub Secrets
API_KEYS = [
    os.environ.get("GEMINI_KEY_1"),
    os.environ.get("GEMINI_KEY_2"),
    os.environ.get("GEMINI_KEY_3")
]

# --- 1. SCRAPING ENGINE ---
def scrape_reader_mode(url):
    """Fetches clean text using Reader Mode."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        doc = Document(resp.text)
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        print(f"Scrape error for {url}: {e}")
        return ""

def get_hindu_editorials():
    print("📰 Fetching The Hindu...")
    rss_url = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"
    resp = requests.get(rss_url)
    root = ET.fromstring(resp.content)
    
    editorials = []
    for item in root.findall('.//item')[:2]:
        link = item.find('link').text
        text = scrape_reader_mode(link)
        editorials.append(text)
    return editorials

def get_indian_express_editorials():
    print("📰 Fetching The Indian Express...")
    rss_url = "https://indianexpress.com/section/opinion/editorials/feed/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(rss_url, headers=headers)
    root = ET.fromstring(resp.content)
    
    scraped_articles = []
    # Grab up to the latest 3 editorials
    for item in root.findall('.//item')[:3]:
        link = item.find('link').text
        text = scrape_reader_mode(link)
        if text:
            scraped_articles.append({
                "link": link,
                "text": text,
                "length": len(text)
            })
            
    # 🔥 THE MAGIC SORT: Sort by length descending, then grab the top 2
    scraped_articles.sort(key=lambda x: x["length"], reverse=True)
    top_2 = scraped_articles[:2]
    
    return [article["text"] for article in top_2]

# --- 2. GEMINI BULLDOZER (KEY ROTATION) ---
def call_gemini_with_rotation(prompt):
    """Tries 3 keys in sequence to bypass rate limits."""
    for i, key in enumerate(API_KEYS):
        if not key: continue
        try:
            print(f"🤖 Attempting with Key {i+1}...")
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.4)
            )
            return response.text.strip()
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                print(f"⚠️ Key {i+1} Exhausted. Rotating...")
                continue
            else:
                print(f"⚠️ Error with Key {i+1}: {e}")
                time.sleep(2)
    raise Exception("🚨 All API keys failed or are exhausted!")

# --- 3. THE 4-STAGE PIPELINE ---
def run_vocab_pipeline():
    # 1. Gather all 4 Editorials
    hindu_texts = get_hindu_editorials()
    ie_texts = get_indian_express_editorials()
    massive_context = "\n\n---\n\n".join(hindu_texts + ie_texts)
    
    # Load your exact prompts (Paste your massive prompts here)
    PROMPT_1_EXTRACT = f"""[INSERT YOUR SOURCE 13 PROMPT HERE]\n\nEDITORIAL:\n{massive_context}"""
    
    print("🧠 Stage 1: Extracting Candidates...")
    candidates = call_gemini_with_rotation(PROMPT_1_EXTRACT)
    time.sleep(3) # Short breather for the API
    
    PROMPT_2_FILTER = f"""[INSERT YOUR SOURCE 14 PROMPT HERE]\n\nINPUT:\n{candidates}"""
    print("🧠 Stage 2: Filtering Top 25...")
    top_25 = call_gemini_with_rotation(PROMPT_2_FILTER)
    time.sleep(3)
    
    PROMPT_3_GENERATE = f"""[INSERT YOUR SOURCE 15 PROMPT HERE]\n\nINPUT WORDS:\n{top_25}"""
    print("🧠 Stage 3: Generating JSON Quiz...")
    raw_json = call_gemini_with_rotation(PROMPT_3_GENERATE)
    
    # Strip markdown code blocks if Gemini added them
    raw_json = raw_json.replace("```json", "").replace("```", "").strip()
    time.sleep(3)
    
    PROMPT_4_QA = f"""[INSERT YOUR SOURCE 12 PROMPT HERE]\n\nINPUT JSON:\n{raw_json}"""
    print("🧠 Stage 4: Quality Review & Auto-Correction...")
    final_json = call_gemini_with_rotation(PROMPT_4_QA)
    final_json = final_json.replace("```json", "").replace("```", "").strip()
    
    # Save the flawless quiz
    with open('questions.json', 'w', encoding='utf-8') as f:
        f.write(final_json)
    print("✅ Successfully built and saved questions.json!")

if __name__ == "__main__":
    run_vocab_pipeline()
