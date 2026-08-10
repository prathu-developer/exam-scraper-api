import sys
import requests
from bs4 import BeautifulSoup # type: ignore
import json
import xml.etree.ElementTree as ET
from readability import Document # type: ignore
import os
import time
from google import genai
from google.genai import types # type: ignore

# Load keys safely from GitHub Secrets
API_KEYS = [
    os.environ.get("GEMINI_KEY_1"),
    os.environ.get("GEMINI_KEY_2"),
    os.environ.get("GEMINI_KEY_3")
]

# ✨ Define models for rotation and fallback
MODELS = [
    'gemini-3.6-flash',
    'gemini-3.5-flash'
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
    # Fetch exactly 2 editorials from The Hindu
    for item in root.findall('.//item')[:2]:
        link = item.find('link').text
        text = scrape_reader_mode(link)
        editorials.append(text)
    return editorials

# --- 2. GEMINI BULLDOZER (KEY ROTATION & RETRY) ---
def call_gemini_with_rotation(prompt):
    """Tries keys and models to handle rate limits or server overloads."""
    max_retries = 3
    
    for attempt in range(max_retries):
        for i, key in enumerate(API_KEYS):
            if not key: continue
            client = genai.Client(api_key=key)
            
            for model_name in MODELS:
                try:
                    print(f"🤖 Attempting with Key {i+1} using {model_name} (Attempt {attempt+1}/{max_retries})...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.4)
                    )
                    return response.text.strip()
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # Handle standard API rate limits
                    if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                        print(f"⚠️ Key {i+1} ({model_name}) Quota Exhausted. Rotating to fallback model/key...")
                        continue
                        
                    # Handle Google Server Overloads
                    elif "503" in error_msg or "unavailable" in error_msg:
                        print(f"⚠️ Google Server Overloaded (503) on {model_name}. Waiting 30 seconds...")
                        time.sleep(30)
                        continue 
                        
                    # Handle any other network errors
                    else:
                        print(f"⚠️ Error on Key {i+1} ({model_name}): {e}")
                        time.sleep(5)
                    
    raise Exception("🚨 All API keys and model fallbacks failed due to sustained errors. Try again later!")

# --- TELEGRAM PREVIEW SENDER ---
def send_telegram_preview(final_json_string):
    """Sends a short confirmation DM to the Admin with a GitHub link."""
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
    
    try:
        quiz_data = json.loads(final_json_string)
        
        message_text = "✅ **VOCAB QUIZ SUCCESSFULLY GENERATED!**\n\n"
        message_text += f"🎯 Extracted, formatted, and QA-checked **{len(quiz_data)}** advanced vocabulary questions.\n\n"
        message_text += "🔗 **View the final JSON file here:**\n"
        message_text += "https://github.com/prathu-developer/exam-scraper-api/blob/main/questions.json"
        
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": message_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })
            
        print("📲 Telegram DM confirmation sent to Admin successfully!")
    except Exception as e:
        print(f"⚠️ Failed to send Telegram preview: {e}")

# --- 3. THE 4-STAGE PIPELINE ---
def run_vocab_pipeline():
    # 1. Gather ONLY 2 Hindu Editorials
    hindu_texts = get_hindu_editorials()
    massive_context = "\n\n---\n\n".join(hindu_texts)
    
    # 💾 Create the Audit Log and save the raw editorials
    with open('vocab_audit_log.md', 'w', encoding='utf-8') as log_file:
        log_file.write("# 🧠 Vocab Generation Audit Log\n\n## 📰 PREP: Raw Editorials\n```text\n" + massive_context + "\n```\n\n")
        
    PROMPT_1_EXTRACT = f"""[ROLE]
You are a Senior Lexicographer extracting advanced vocabulary for a competitive exam database.

[OBJECTIVE]
Extract a comprehensive, high-volume list of challenging vocabulary from the text. 
Your goal is to build a massive pool of candidates (aim for 40 to 60+ words if the text allows). Do not be overly restrictive during this extraction phase.

[TARGET PROFILE - WHAT TO EXTRACT]
Be highly inclusive of words that fit this profile:
- Advanced, descriptive verbs (e.g., 'exfiltrated', 'obfuscate', 'ameliorate')
- Sophisticated adjectives and adverbs (e.g., 'contentious', 'opaque', 'fastidious')
- Abstract nouns indicating mature themes (e.g., 'lacunae', 'milieu', 'hegemony')
- High-level idioms and phrasal verbs.

[EXCLUSIONS - KEEP IT SIMPLE]
Skip only the absolute basics:
- Everyday foundational words (e.g., 'said', 'good', 'market', 'wealth', 'facility')
- Proper nouns, dates, and numbers.
- Basic prepositions or transition phrases.

[FORMATTING]
1. Standardise all extracted spellings strictly to British English (e.g., 'prioritise', 'rigour').
2. Return ONLY a numbered list of the extracted words/phrases in lowercase. 
3. Do not include definitions or extra text.

[EDITORIAL TEXT]
{massive_context}"""
    
    print("🧠 Stage 1: Extracting Candidates...")
    candidates = call_gemini_with_rotation(PROMPT_1_EXTRACT)
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## 🎯 PROMPT 1: All Extracted Candidates\n```text\n" + candidates + "\n```\n\n")
        
    time.sleep(3) # Short breather for the API
    
    PROMPT_2_FILTER = f"""[ROLE]
You are a Senior Lexicographer and Competitive Exam Paper Setter for SSC CGL Tier-II and IBPS PO Mains.

[OBJECTIVE]
Filter the unfiltered list of candidates and select EXACTLY 15 high-learning-value words. 

[HIGH LEARNING-VALUE CRITERIA]
- PRIORITISE: Words that genuinely test vocabulary depth (e.g., 'lacunae', 'exacerbate', 'anachronism', 'contentious', 'capricious', 'obfuscate').
- STRICTLY BAN COMMON EDITORIAL FILLER: Do NOT select common words that appear frequently but have low testing value. Ban words like: 'robust', 'persistent', 'elevated', 'pertain', 'compelled', 'scrutiny', 'ensure', 'significantly', 'operational'. If an average student can guess the meaning in context, discard it.
- STANDARDISATION: Convert all words to strict British English spelling.

[STRICT OUTPUT FORMAT]
Return EXACTLY 15 items. No conversational text, no markdown code blocks, no numbering. Separate each item with a single blank line.

Word: <word>
Part of Speech: <Noun | Verb | Adjective | Adverb | Phrasal Verb | Idiom>

[INPUT CANDIDATES]
{candidates}"""
    print("🧠 Stage 2: Filtering Top 15...")
    top_15 = call_gemini_with_rotation(PROMPT_2_FILTER)
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## 🏆 PROMPT 2: Filtered Top 15 Finalists\n```text\n" + top_15 + "\n```\n\n")
        
    time.sleep(3)
    
    PROMPT_3_GENERATE = f"""[ROLE]
You are an expert Question Setter for top-tier Indian government examinations (SSC CGL Tier-II, IBPS PO Mains, RBI Grade B). Generate a JSON array of 15 precise vocabulary questions.

[QUESTION ALLOCATION]
Questions 1-10: "What is the SIMILAR meaning of '[Word]'?"
Questions 11-15: "What is the OPPOSITE meaning of '[Word]'?"

[CORE EXAM PRINCIPLES (CRITICAL)]
1. EDITORIAL CONTEXT IS KING: Always select the meaning intended in the editorial/figurative usage rather than the most literal definition (e.g., 'spiralling' -> 'escalating').
2. THE 'GOLDILOCKS' VOCABULARY ZONE: Target B2/C1 editorial English (e.g., The Hindu). DO NOT inflate difficulty by using obscure C2, GRE, or GMAT vocabulary. 
   - Acceptable: 'inadequate', 'ambiguous', 'instrument', 'spoil'.
   - STRICTLY FORBIDDEN (Too Obscure): 'exiguous', 'paucitous', 'civocracy', 'vitiate', 'polemical'.
   - Do not reject a highly accurate, common synonym just because it seems "easy". Exam realism is more important than dictionary sophistication.
3. TRUE LEXICAL OPPOSITES: Antonyms must be semantic opposites, not role-based (Do not pair 'junta' with 'democracy'). 

[DISTRACTOR DESIGN FORMULA]
1. PLAUSIBLE EXAM REALISM: Distractors must be standard, realistic competitive exam options. Do not use bizarre, archaic, or hyper-academic words.
2. SEMANTIC PROXIMITY: Distractors should belong to the same general topic or emotional tone as the correct answer to prevent easy elimination, but must be definitively incorrect.
3. SAME PART OF SPEECH: All four options must strictly match the target word's part of speech.
4. BRITISH ENGLISH: Use strict British English spelling for all options and explanations (e.g., 'emphasises', 'favour').

[OUTPUT FORMAT]
Return a valid JSON array only. No markdown, no introductory text. 
Ensure EXACTLY 4 options are provided per question. Do NOT include question numbers in the "question" string.

[
{{
"question":"What is the SIMILAR meaning of 'Word'?",
"options":[
"Option A",
"Option B",
"Option C",
"Option D"
],
"correct_answer":"Exact option text",
"explanation":"Provide a comprehensive and detailed explanation. Explain the specific editorial context, why the correct answer fits, why distractors fail, and include nuance or usage notes."
}}
]

[INPUT WORDS]
{top_15}"""
    print("🧠 Stage 3: Generating JSON Quiz...")
    raw_json = call_gemini_with_rotation(PROMPT_3_GENERATE)
    
    # Strip markdown code blocks if Gemini added them
    raw_json = raw_json.replace("```json", "").replace("```", "").strip()
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## ⚙️ PROMPT 3: Raw Unchecked JSON\n```json\n" + raw_json + "\n```\n\n")
        
    time.sleep(3)
    
    PROMPT_4_QA = f"""[ROLE]
You are the Chief Quality Reviewer for high-level competitive exams (SSC CGL, IBPS PO). Audit this JSON quiz for absolute contextual accuracy and exam realism.

[QA COMPLIANCE CHECKLIST]
Review every question independently. If a question fails any test, you MUST rewrite ALL options before outputting the final JSON. Ensure EXACTLY 4 options exist for every question.

1. THE GRE/GMAT INFLATION AUDIT: Check the correct answer and distractors. Are any of them unnecessarily rare, archaic, or hyper-academic (e.g., 'exiguous', 'civocracy', 'paucitous', 'vitiate')? If YES, rewrite the options using natural, standard SSC/Banking vocabulary (e.g., 'inadequate', 'spoil'). Choose exam realism over dictionary sophistication.
2. CONTEXTUAL MEANING: Ensure the synonym/antonym matches the figurative/editorial use of the word (e.g., 'Spiralling' -> 'Escalating'), not the literal/physical meaning.
3. THE ELIMINATION TEST: Check the three incorrect distractors. Are they completely unrelated to the target word, making elimination too easy? If YES, rewrite the distractors using standard words from the SAME semantic field.
4. BRITISH ENGLISH VERIFICATION: Ensure all text, options, and explanations conform strictly to British English standards.

[OUTPUT FORMAT]
Return ONLY the corrected JSON array. Do not use Markdown syntax blocks (```json). No commentary. Ensure there are no question numbers in the "question" fields.

[INPUT JSON]
{raw_json}"""
    print("🧠 Stage 4: Quality Review & Auto-Correction...")
    final_json = call_gemini_with_rotation(PROMPT_4_QA)
    final_json = final_json.replace("```json", "").replace("```", "").strip()
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## ✅ PROMPT 4: Final Flawless JSON\n```json\n" + final_json + "\n```\n\n")
        
    # Save the flawless quiz
    with open('questions.json', 'w', encoding='utf-8') as f:
        f.write(final_json)
    print("✅ Successfully built and saved questions.json!")

if __name__ == "__main__":
    try:
        run_vocab_pipeline()
    except Exception as e:
        BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"[https://api.telegram.org/bot](https://api.telegram.org/bot){BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"🚨 **CRITICAL ERROR (Vocab Generator):**\nYour GitHub Action failed to generate today's vocabulary!\n\n`{e}`",
                "parse_mode": "Markdown"
            })
        print(f"Fatal pipeline error: {e}")
        sys.exit(1) # <--- THIS STOPS GITHUB ACTIONS FROM CONTINUING
