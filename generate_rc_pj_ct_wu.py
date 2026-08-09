import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime
from google import genai
from google.genai import types

# --- 1. SETUP CREDENTIALS ---
API_KEYS = [
    os.environ.get("GEMINI_KEY_4"),
    os.environ.get("GEMINI_KEY_5"),
    os.environ.get("GEMINI_KEY_6")
]
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

def log_audit(step, details):
    """Writes the step-by-step process to the audit log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{step}] {details}\n"
    with open("comprehension_audit_log.txt", "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

# --- 2. SCRAPING ENGINE (THE HINDU ONLY) ---
def scrape_reader_mode(url):
    """Fetches clean text using Reader Mode."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        doc = Document(resp.text)
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        log_audit("SCRAPE_ERROR", f"Error for {url}: {e}")
        return ""

def get_hindu_editorials():
    log_audit("FETCH", "Fetching exactly 2 editorials from The Hindu...")
    rss_url = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"
    resp = requests.get(rss_url)
    root = ET.fromstring(resp.content)
    
    editorials = []
    for item in root.findall('.//item')[:2]:
        link = item.find('link').text
        title = item.find('title').text
        text = scrape_reader_mode(link)
        editorials.append({"title": title, "text": text})
    return editorials

# --- 3. BULLDOZER (AI GENERATION) ---
def call_gemini_for_set(prompt, set_name):
    """Tries keys and handles rate limits to generate a full JSON set block."""
    max_retries = 3
    
    for attempt in range(max_retries):
        for i, key in enumerate(API_KEYS):
            if not key: continue
            try:
                log_audit("API_CALL", f"Generating {set_name} with Key {i+1} (Attempt {attempt+1}/{max_retries})...")
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.5) # Slightly higher temp for creative distractors
                )
                
                raw_text = response.text.strip()
                # Clean markdown blocks to parse JSON
                clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(clean_json_str)
                
                log_audit("SUCCESS", f"Successfully generated valid JSON for {set_name}.")
                return parsed_json
                
            except json.JSONDecodeError:
                log_audit("API_WARN", f"[{set_name}] Key {i+1} returned invalid JSON. Retrying...")
                time.sleep(3)
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg:
                    log_audit("API_WARN", f"[{set_name}] Key {i+1} exhausted. Rotating...")
                    continue
                elif "503" in error_msg or "unavailable" in error_msg:
                    log_audit("API_WARN", f"[{set_name}] 503 Overload on Key {i+1}. Waiting 30s...")
                    time.sleep(30)
                    continue
                else:
                    log_audit("API_WARN", f"[{set_name}] Unknown error: {e}")
                    time.sleep(5)
                    
    raise Exception(f"🚨 Failed to generate {set_name} after all retries and key rotations.")

# --- 4. MAIN PIPELINE ---
def main():
    log_audit("START", "🚀 Initializing Comprehension & Usage Script...")

    editorials = get_hindu_editorials()
    if len(editorials) < 2:
        raise ValueError("Failed to fetch 2 editorials from The Hindu.")

    # Prepare texts
    ed1_text = editorials[0]['text']
    ed2_text = editorials[1]['text']

    # Split Editorial 2 in half for Cloze and Para Jumbles
    ed2_sentences = [s.strip() + '.' for s in ed2_text.split('.') if s.strip()]
    mid_point = len(ed2_sentences) // 2
    ed2_first_half = " ".join(ed2_sentences[:mid_point])
    ed2_second_half = " ".join(ed2_sentences[mid_point:])

    log_audit("TEXT_PREP", "Editorial 2 split successfully. First half for Cloze, second half for Para Jumbles.")

    # --- 5. TIMETABLE LOGIC ---
    # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    current_day = datetime.now().weekday()
    final_output = {"date": datetime.now().strftime("%Y-%m-%d")}

    # ---------------------------------------------------------
    # SET D: READING COMPREHENSION (Mon=0, Thu=3)
    # ---------------------------------------------------------
    if current_day in [0, 3]:
        prompt_rc = f"""[ROLE]
You are an expert Question Setter for top-tier Indian competitive exams (SSC CGL Tier-II, Banking PO, RBI Grade B). 

[TASK]
Create exactly 8 Reading Comprehension questions based on the provided editorial. 
Ensure the passage is kept intact. Do NOT make the questions unnecessarily difficult just to appear advanced. Questions must be practical and exam-oriented.

[QUESTION DISTRIBUTION]
Q1, Q2 - Direct/Factual comprehension
Q3, Q4 - Inference (answerable from passage, no outside knowledge)
Q5 - Main Idea / Central Argument
Q6 - Tone / Author's Purpose
Q7 - Vocabulary/phrase in context (meaning as used in the passage)
Q8 - Statement-based comprehension

[DIFFICULTY]
2 Easy, 3 Moderate, 3 Moderate-Hard. Every question must have EXACTLY 4 options and ONE unquestionably correct answer.

[TEXT]
{ed1_text}

[OUTPUT FORMAT]
Return ONLY a valid JSON object matching this exact structure:
{{
    "type": "reading_comprehension",
    "source_editorial": 1,
    "passage": "<INSERT EXACT FULL TEXT HERE>",
    "questions": [
        {{
            "question_type": "direct",
            "question": "According to the passage...",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "Exact option text",
            "explanation": "Brief explanation"
        }}
        // ... 8 questions total
    ]
}}"""
        final_output["set_d"] = call_gemini_for_set(prompt_rc, "Reading Comprehension")
        time.sleep(10)

    # ---------------------------------------------------------
    # SET F: PARA JUMBLES (Tue=1, Fri=4)
    # ---------------------------------------------------------
    if current_day in [1, 4]:
        prompt_pj = f"""[ROLE]
You are an expert Question Setter for SSC CGL Tier-II and Banking PO exams.

[TASK]
Create exactly 5 Para Jumble questions. 
Use the themes, arguments, facts, or ideas from the provided text to construct ORIGINAL coherent paragraphs. Do NOT simply take five consecutive sentences from the text and shuffle them. The student should solve the paragraph through logical relationships (Pronoun reference, Cause/Effect, Chronology), not by remembering the original text.

[CONSTRAINTS]
- 5 Questions total.
- EACH question must contain exactly 5 sentences (Labelled A, B, C, D, E).
- Provide EXACTLY 4 sequence options per question (e.g., "B-E-A-C-D").
- There must be ONE clearly defensible correct sequence.
- Difficulty: Q1, Q2 Moderate | Q3 Moderate-Hard | Q4, Q5 Hard.

[SOURCE TEXT (For inspiration)]
{ed2_second_half}

[OUTPUT FORMAT]
Return ONLY a valid JSON object matching this exact structure:
{{
    "type": "para_jumbles",
    "questions": [
        {{
            "question_number": 1,
            "instruction": "Arrange the following sentences to form a coherent paragraph.",
            "sentences": {{ "A": "...", "B": "...", "C": "...", "D": "...", "E": "..." }},
            "options": ["B-E-A-C-D", "E-B-C-A-D", "B-A-E-D-C", "A-B-E-C-D"],
            "correct_answer": "B-E-A-C-D",
            "explanation": "B introduces the topic. E follows by..."
        }}
        // ... 5 questions total
    ]
}}"""
        final_output["set_f"] = call_gemini_for_set(prompt_pj, "Para Jumbles")
        time.sleep(10)

    # ---------------------------------------------------------
    # SET E: CLOZE TEST (Wed=2, Sat=5)
    # ---------------------------------------------------------
    if current_day in [2, 5]:
        prompt_cloze = f"""[ROLE]
You are an expert Question Setter for SSC CGL Tier-II and Banking PO exams.

[TASK]
Create ONE continuous Cloze Test passage using the provided text. Take a coherent section (approx 180-250 words) and create EXACTLY 8 blanks. 
The passage must remain natural and readable after blanks (denoted as {{1}}, {{2}}, etc.) are inserted.

[BLANK DISTRIBUTION]
Test different skills across the 8 blanks: Vocabulary, Grammar, Collocation, Prepositions, Connectors, Verb Forms.
At least 2 distractor options per blank should appear genuinely plausible. Every blank must have EXACTLY 4 options and ONE unquestionably best answer.

[TEXT]
{ed2_first_half}

[OUTPUT FORMAT]
Return ONLY a valid JSON object matching this exact structure:
{{
    "type": "cloze_test",
    "source_editorial": 2,
    "passage": "Passage text with {{1}}, {{2}}, {{3}}, {{4}}, {{5}}, {{6}}, {{7}}, {{8}}.",
    "questions": [
        {{
            "blank_number": 1,
            "question_type": "vocabulary",
            "options": ["Opt1", "Opt2", "Opt3", "Opt4"],
            "correct_answer": "Opt1",
            "explanation": "Opt1 fits because..."
        }}
        // ... 8 questions total
    ]
}}"""
        final_output["set_e"] = call_gemini_for_set(prompt_cloze, "Cloze Test")
        time.sleep(10)

    # ---------------------------------------------------------
    # SET G: WORD USAGE (Tue=1, Wed=2, Fri=4, Sat=5)
    # ---------------------------------------------------------
    if current_day in [1, 2, 4, 5]:
        prompt_wu = f"""[ROLE]
You are an expert Question Setter for SSC CGL Tier-II and Banking PO exams.

[TASK]
Create exactly 5 "Word Usage in Context" questions. Extract 5 challenging words from the provided text.
This tests whether the student can correctly USE a word or phrase in a sentence, not just know its definition.

[CONSTRAINTS]
- Format: "Choose the sentence in which [WORD] is used correctly."
- Provide EXACTLY 4 sentence options per question.
- Only ONE sentence should use the word correctly. The incorrect options should be grammatically natural but use the word incorrectly based on context/collocation. Do NOT make incorrect options absurd.

[TEXT SOURCE (Extract words from here)]
{ed1_text}

[OUTPUT FORMAT]
Return ONLY a valid JSON object matching this exact structure:
{{
    "type": "word_usage",
    "questions": [
        {{
            "word": "mitigate",
            "question": "Choose the sentence in which 'mitigate' is used correctly.",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "Exact option text",
            "explanation": "Explanation of correct usage vs wrong ones."
        }}
        // ... 5 questions total
    ]
}}"""
        final_output["set_g"] = call_gemini_for_set(prompt_wu, "Word Usage")

    # --- 6. SAVE FINAL OUTPUT ---
    if len(final_output) > 1: # More than just the date key
        with open("comprehension_tests.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4)
        log_audit("COMPLETE", f"🎉 Finished! Saved scheduled tests to comprehension_tests.json.")
    else:
        log_audit("COMPLETE", "No tests scheduled for today based on the timetable.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"🚨 **CRITICAL ERROR (Comprehension Generator):**\nYour GitHub Action failed to generate today's sets!\n\n`{e}`",
                "parse_mode": "Markdown"
            })
        print(f"Fatal pipeline error: {e}")
        exit(1)
