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

# --- 1. SETUP CREDENTIALS & MODELS ---
API_KEYS = [
    os.environ.get("GEMINI_KEY_4"),
    os.environ.get("GEMINI_KEY_5"),
    os.environ.get("GEMINI_KEY_6")
]
# ✨ NEW: Define the two models you want to rotate
MODELS = [
    'gemini-3.6-flash',
    'gemini-3.5-flash' # Replace with any second model you prefer
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

# --- 3. BULLDOZER (AI GENERATION & VALIDATION) ---
def call_gemini_raw(prompt, step_name):
    """Handles the raw API call with KEY and MODEL rotation."""
    max_retries = 3
    for attempt in range(max_retries):
        for i, key in enumerate(API_KEYS):
            if not key: continue
            
            # ✨ NEW: Rotate through your models for each key
            for model_name in MODELS:
                try:
                    log_audit("API_CALL", f"[{step_name}] Key {i+1} | Model: {model_name} (Attempt {attempt+1}/{max_retries})...")
                    client = genai.Client(api_key=key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.5)
                    )
                    raw_text = response.text.strip()
                    clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
                    return json.loads(clean_json_str)
                except json.JSONDecodeError:
                    log_audit("API_WARN", f"[{step_name}] Key {i+1} ({model_name}) returned invalid JSON. Retrying...")
                    time.sleep(3)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg:
                        # Model quota exhausted, moving to the next model in the list
                        continue
                    elif "503" in error_msg or "unavailable" in error_msg:
                        time.sleep(30)
                        continue
                    else:
                        time.sleep(5)
                        
        raise Exception(f"🚨 Failed during {step_name} after all retries across all keys and models.")

def generate_and_validate(generation_prompt, set_name, validation_rules):
    """Generates the questions, runs them through an AI Validator, and regenerates flaws."""
    # Pass 1: Generate initial set
    raw_json = call_gemini_raw(generation_prompt, f"{set_name} - Generation")
    
    # Pass 2: Validate the set
    val_prompt = f"""[ROLE]
You are an Elite QA Reviewer for SSC CGL and Banking PO examinations.

[TASK]
Review the provided JSON question set. You must enforce the Anti-Elimination Rule: could a student answer correctly by simply eliminating obvious, absurd, or grammatically impossible distractors? Are inference questions heavily dependent on outside knowledge?

[RULES TO ENFORCE]
{validation_rules}

[INPUT JSON]
{json.dumps(raw_json)}

[OUTPUT FORMAT]
Return ONLY valid JSON. If the set is perfect, return: {{"status": "PASS"}}
If any question fails, return: {{"status": "FAIL", "failed_questions": [1, 4], "reasons": {{"1": "Option C is obviously false.", "4": "Requires outside knowledge."}}}}
"""
    validation_result = call_gemini_raw(val_prompt, f"{set_name} - Validation")
    
    if validation_result.get("status") == "PASS":
        log_audit("QA_PASS", f"{set_name} passed quality control perfectly on the first try.")
        return raw_json
        
    # Pass 3: Refine the flawed questions
    log_audit("QA_FAIL", f"{set_name} failed QA. Issues: {validation_result.get('reasons')}. Initiating targeted regeneration...")
    
    refine_prompt = f"""[ROLE]
You are a Senior Question Setter correcting flawed questions.

[TASK]
The following JSON failed Quality Assurance. 
Here are the specific failures: {json.dumps(validation_result.get('reasons'))}

[INSTRUCTIONS]
Rewrite ONLY the options, questions, or explanations for the specific questions that failed. 
Leave all passing questions exactly as they are. 
Ensure the distractors are now highly plausible, semantically related, and strictly adhere to exam-level difficulty.

[INPUT JSON]
{json.dumps(raw_json)}

[OUTPUT FORMAT]
Return ONLY the FULL, corrected JSON object.
"""
    return call_gemini_raw(refine_prompt, f"{set_name} - Regeneration")

def prepare_exam_materials(ed1_text, ed2_text):
    """Analyzes both editorials and routes the most coherent sections to the right tasks."""
    prompt = f"""[ROLE]
You are the Chief Content Editor for an SSC/Banking exam platform.

[TASK]
Analyze two editorials from The Hindu and route them to the correct exam sections based on these strict rules:

[RULES]
1. Assess both editorials. Classify them internally as: EXCELLENT FOR RC, GOOD FOR RC, BETTER FOR VOCAB/USAGE, or POOR FOR RC.
2. Select the BEST editorial for Reading Comprehension (RC).
3. RC PASSAGE: Extract a coherent, continuous passage of approx 500-800 words from the chosen RC editorial. 
   - If the editorial is highly coherent and around that length, use the full text.
   - If it is very long, repetitive, or loses coherence, extract the best continuous block (must contain central argument).
   - DO NOT paraphrase. Keep exact original wording.
4. CLOZE PASSAGE: Using the OTHER editorial, extract a continuous, coherent section of 180-250 words.
5. PARA JUMBLE INSPIRATION: Use the remaining text of the OTHER editorial.

[EDITORIAL 1]
{ed1_text}

[EDITORIAL 2]
{ed2_text}

[CRITICAL INSTRUCTION]
Escape all quotation marks properly inside the JSON string values. Output exact continuous text without altering words.

[OUTPUT FORMAT]
Return ONLY valid JSON matching this exact structure:
{{
    "rc_editorial_id": 1, 
    "rc_passage": "Exact extracted text for RC...",
    "cloze_editorial_id": 2,
    "cloze_passage": "Exact extracted 180-250 words for Cloze...",
    "pj_inspiration_text": "Remaining text from the cloze editorial...",
    "wu_source_text": "Full text of the RC editorial..."
}}"""
    return call_gemini_raw(prompt, "Material Prep & AI Content Routing")

# --- 4. MAIN PIPELINE ---
def main():
    log_audit("START", "🚀 Initializing Advanced Comprehension Pipeline...")

    # --- TIMETABLE CHECK ---
    current_day = datetime.now().weekday()
    # TEMPORARILY COMMENTED OUT FOR SUNDAY TEST
    # if current_day == 6: # Sunday (0=Mon, 6=Sun)
    #     log_audit("COMPLETE", "No tests scheduled for today based on the timetable. Exiting.")
    #     return

    editorials = get_hindu_editorials()
    if len(editorials) < 2:
        raise ValueError("Failed to fetch 2 editorials from The Hindu.")

    ed1_text = editorials[0]['text']
    ed2_text = editorials[1]['text']

    # --- AI CONTENT ROUTING ---
    log_audit("TEXT_PREP", "Routing editorials through AI for dynamic suitability analysis and passage extraction...")
    materials = prepare_exam_materials(ed1_text, ed2_text)
    
    # Safely extract materials with fallbacks just in case
    rc_passage = materials.get("rc_passage", ed1_text)
    rc_source_id = materials.get("rc_editorial_id", 1)
    
    cloze_text = materials.get("cloze_passage", ed2_text)
    cloze_source_id = materials.get("cloze_editorial_id", 2)
    
    pj_text = materials.get("pj_inspiration_text", ed2_text)
    wu_text = materials.get("wu_source_text", ed1_text)

    final_output = {"date": datetime.now().strftime("%Y-%m-%d")}

    # ---------------------------------------------------------
    # SET D: READING COMPREHENSION (Mon=0, Thu=3)
    # ---------------------------------------------------------
    if True: # Changed from: if current_day in [0, 3]:
        rc_rules = """- Exactly 8 questions. Difficulty: 2 Easy, 3 Moderate, 3 Mod-Hard.
- Rotate question types (Direct, Inference, Main Idea, Tone, Contextual Vocab).
- Distractors must be highly plausible and similar in length/specificity.
- NO questions solvable by simple keyword matching.
- Explanations must justify why the answer is correct and why a tempting distractor is wrong."""

        prompt_rc = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create an 8-question RC test using the strategically extracted exam passage provided below.
[RULES] {rc_rules}
[PASSAGE] 
{rc_passage}
[OUTPUT FORMAT] Return a JSON object matching standard schema with 'type': 'reading_comprehension', 'source_editorial': {rc_source_id}, and 'passage': "<INSERT THE EXACT EXACT PASSAGE PROVIDED ABOVE>". Do not alter the passage."""
        
        final_output["set_d"] = generate_and_validate(prompt_rc, "Reading Comprehension", rc_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET F: PARA JUMBLES (Tue=1, Fri=4)
    # ---------------------------------------------------------
    if True: # Changed from: if current_day in [1, 4]:
        pj_rules = """- Exactly 5 questions. Each must contain 5 sentences (A,B,C,D,E).
- Difficulty: 2 Moderate, 1 Mod-Hard, 2 Hard.
- Sentences must form original, coherent paragraphs based on the text's themes (do not just copy/shuffle text).
- Must contain strong logical relationships (pronouns, cause/effect, chronology).
- Only ONE defensible correct sequence."""

        prompt_pj = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create 5 Para Jumble questions.
[RULES] {pj_rules}
[SOURCE THEMES (For Inspiration)] 
{pj_text}
[OUTPUT FORMAT] Return a JSON object matching standard schema with 'type': 'para_jumbles'."""
        
        final_output["set_f"] = generate_and_validate(prompt_pj, "Para Jumbles", pj_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET E: CLOZE TEST (Wed=2, Sat=5)
    # ---------------------------------------------------------
    if True: # Changed from: if current_day in [2, 5]:
        cloze_rules = """- Exactly 8 blanks injected into the text.
- Distribution: 2 Vocab, 1 Collocation, 1 Connector, 1 Preposition, 1 Verb Form, 1 Grammar, 1 Meaning.
- At least 3 blanks must require reading the entire surrounding sentence to answer.
- Distractors must be grammatically plausible (unless grammar is the exact skill tested). No absurd options."""

        prompt_cloze = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create a Cloze Test using the provided coherent text block.
[RULES] {cloze_rules}
[TEXT] 
{cloze_text}
[OUTPUT FORMAT] Return a JSON object matching standard schema with 'type': 'cloze_test', and 'source_editorial': {cloze_source_id}."""
        
        final_output["set_e"] = generate_and_validate(prompt_cloze, "Cloze Test", cloze_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET G: WORD USAGE (Tue=1, Wed=2, Fri=4, Sat=5)
    # ---------------------------------------------------------
    if True: # Changed from: if current_day in [1, 2, 4, 5]:
        wu_rules = """- 5 questions testing advanced usage of vocabulary found in the text.
- Format: "Choose the sentence in which [WORD] is used correctly."
- ALL 4 options must be grammatically natural. Incorrect options must fail due to improper contextual meaning, poor collocation, or incorrect prepositions.
- A student cannot eliminate incorrect options merely by spotting bad grammar."""

        prompt_wu = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Extract 5 challenging words from the text and create Word Usage questions.
[RULES] {wu_rules}
[TEXT] 
{wu_text}
[OUTPUT FORMAT] Return a JSON object matching standard schema with 'type': 'word_usage'."""
        
        final_output["set_g"] = generate_and_validate(prompt_wu, "Word Usage", wu_rules)

    # --- 6. SAVE FINAL OUTPUT ---
    if len(final_output) > 1:
        with open("comprehension_tests.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4)
        log_audit("COMPLETE", f"🎉 Finished! Saved robust, QA-validated tests to comprehension_tests.json.")
    else:
        log_audit("COMPLETE", "No tests scheduled for today based on the timetable.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"🚨 **CRITICAL ERROR (Comprehension Generator):**\nPipeline failure!\n\n`{e}`",
                "parse_mode": "Markdown"
            })
        print(f"Fatal pipeline error: {e}")
        exit(1)
