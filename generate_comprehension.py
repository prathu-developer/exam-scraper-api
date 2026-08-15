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
MODELS = [
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash'
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
                        continue
                    elif "503" in error_msg or "unavailable" in error_msg:
                        time.sleep(30)
                        continue
                    else:
                        time.sleep(5)
                        
        raise Exception(f"🚨 Failed during {step_name} after all retries across all keys and models.")

def generate_and_validate(generation_prompt, set_name, validation_rules, max_refinements=3):
    """Generates the questions, runs them through an AI Validator, and regenerates flaws with looping."""
    # Pass 1: Generate initial set
    raw_json = call_gemini_raw(generation_prompt, f"{set_name} - Generation")
    
    # Loop for Validation and Targeted Regeneration
    for attempt in range(max_refinements):
        val_prompt = f"""[ROLE]
You are an Elite QA Reviewer for SSC CGL and Banking PO examinations.

[TASK]
Review the provided JSON question set against the strict validation rules. 

[CRITICAL INSTRUCTIONS]
- Ensure NO option is referenced by position or letters (A, B, C, D) inside the "options" array.
- Ensure the "options" field is a simple flat array of strings (e.g., ["Option 1", "Option 2"]).
- Ensure "correct_answer" is the exact string matching one of the options.
- Check that the explanation relies solely on passage meaning, not option letters.

[RULES TO ENFORCE]
{validation_rules}

[INPUT JSON]
{json.dumps(raw_json)}

[OUTPUT FORMAT]
Return ONLY valid JSON. If the set is perfect, return: {{"status": "PASS"}}
If any question fails, return exact failure reasons to feed a regeneration prompt: 
{{"status": "FAIL", "failed_questions": [1, 4], "reasons": {{"1": "options array contains 'A.', 'B.' prefixes.", "4": "Explanation relies on general knowledge."}}}}
"""
        validation_result = call_gemini_raw(val_prompt, f"{set_name} - Validation (Attempt {attempt+1})")
        
        if validation_result.get("status") == "PASS":
            log_audit("QA_PASS", f"{set_name} passed quality control perfectly on attempt {attempt+1}.")
            return raw_json
            
        # Pass 3: Refine the flawed questions
        log_audit("QA_FAIL", f"{set_name} failed QA. Issues: {validation_result.get('reasons')}. Initiating targeted regeneration...")
        
        refine_prompt = f"""[ROLE]
You are a Senior Question Setter correcting flawed questions.

[TASK]
The following JSON failed Quality Assurance. 
Here are the exact failure reasons: {json.dumps(validation_result.get('reasons'))}

[INSTRUCTIONS]
Rewrite ONLY the options, questions, or explanations for the specific questions that failed. 
Pass the exact failure reason into your fixes. Leave all passing questions exactly as they are. 
Ensure the distractors are now highly plausible, semantically related, and strictly adhere to exam-level difficulty.
Maintain the exact required schema using flat "options" arrays and "correct_answer".

[INPUT JSON]
{json.dumps(raw_json)}

[OUTPUT FORMAT]
Return ONLY the FULL, corrected JSON object.
"""
        raw_json = call_gemini_raw(refine_prompt, f"{set_name} - Regeneration (Attempt {attempt+1})")
    
    log_audit("QA_WARN", f"{set_name} max refinements reached. Saving last iteration.")
    return raw_json

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

    current_day = datetime.now().weekday()
    if current_day == 6: 
        log_audit("COMPLETE", "No tests scheduled for today based on the timetable. Exiting.")
        return

    editorials = get_hindu_editorials()
    if len(editorials) < 2:
        raise ValueError("Failed to fetch 2 editorials from The Hindu.")

    ed1_text = editorials[0]['text']
    ed2_text = editorials[1]['text']

    log_audit("TEXT_PREP", "Routing editorials through AI for dynamic suitability analysis and passage extraction...")
    materials = prepare_exam_materials(ed1_text, ed2_text)
    
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
    if current_day in [0, 3]:
        rc_rules = """### JSON SCHEMA & RANDOMISATION RULES
- Output a flat array of strings for "options". DO NOT use "A.", "B.", "C.", or "D.".
- The "correct_answer" must be the exact string of the correct option.
- Provide a detailed "explanation" without referencing option letters.
- The root object MUST contain: "instruction": "Directions: Read the following passage carefully and answer the questions given below."

### QUESTION BLUEPRINT (Exactly 8 Questions)
1. Main Idea: Core theme of the passage.
2. Inference: Must logically follow from text.
3. Direct: Directly verifiable from text.
4. Tone: The author's underlying attitude.
5. Contextual Vocab: Meaning of a specific word as used.
6. Author's Argument: Identifying central reasoning.
7. Logical Consequence: Applying passage facts to outcome.
8. Inference: Secondary deduction."""

        prompt_rc = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create an 8-question RC test using the strategically extracted exam passage provided below.
[RULES] 
{rc_rules}
[PASSAGE] 
{rc_passage}
[OUTPUT FORMAT] 
Return EXACTLY this JSON structure:
{{
  "type": "reading_comprehension",
  "instruction": "Directions: Read the following passage carefully and answer the questions given below.",
  "passage": "<INSERT EXACT PASSAGE HERE>",
  "questions": [
    {{
      "question": "What is the central idea of the passage?",
      "options": ["Option 1 text", "Option 2 text", "Option 3 text", "Option 4 text"],
      "correct_answer": "Option 2 text",
      "explanation": "Detailed reasoning here..."
    }}
  ]
}}"""
        final_output["set_d"] = generate_and_validate(prompt_rc, "Reading Comprehension", rc_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET F: PARA JUMBLES (Tue=1, Fri=4)
    # ---------------------------------------------------------
    if current_day in [1, 4]:
        pj_rules = """### JSON SCHEMA & RANDOMISATION RULES
- You must create EXACTLY 5 questions based on a SINGLE set of 6 sentences (A, B, C, D, E, F).
- Sentence A must be logically fixed as the FIRST sentence. Sentences B through F must be the jumbled remaining parts of the paragraph.
- EVERY question object in the JSON must include a "sentences" dictionary containing the exact same 6 sentences: {"A": "...", "B": "...", "C": "...", "D": "...", "E": "...", "F": "..."}.
- Ask exactly these 5 distinct questions:
  1. "Which sentence should come immediately after Sentence A?"
  2. "Which sentence should come immediately before Sentence B?"
  3. "Which sentence should be the last sentence of the paragraph?"
  4. "Which of the following is the correct sequence of the remaining sentences?"
  5. "Which pair of sentences forms the most logical consecutive pair?"
- Options must just be the letters or sequences (e.g., "B", "C", "D-F-C-B-E", "F-B"). DO NOT prepend "A.", "B." to the options.
- The root object MUST contain: "instruction": "Directions: In the following question, six sentences are given. Sentence A is fixed in its correct position. The remaining five sentences need to be rearranged to form a coherent paragraph. Answer the questions that follow." """

        prompt_pj = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create 5 Para Jumble questions based on 1 fixed paragraph.
[RULES] {pj_rules}
[SOURCE THEMES (For Inspiration)] 
{pj_text}
[OUTPUT FORMAT] 
Return EXACTLY this JSON structure:
{{
  "type": "para_jumbles",
  "instruction": "Directions: In the following question, six sentences are given. Sentence A is fixed in its correct position. The remaining five sentences need to be rearranged to form a coherent paragraph. Answer the questions that follow.",
  "questions": [
    {{
      "sentences": {{
        "A": "First fixed sentence...",
        "B": "Jumbled part...",
        "C": "Jumbled part...",
        "D": "Jumbled part...",
        "E": "Jumbled part...",
        "F": "Jumbled part..."
      }},
      "question": "Which sentence should come immediately after Sentence A?",
      "options": ["B", "C", "D", "E"],
      "correct_answer": "C",
      "explanation": "Sentence C continues the thought by..."
    }}
  ]
}}"""
        
        final_output["set_f"] = generate_and_validate(prompt_pj, "Para Jumbles", pj_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET E: CLOZE TEST (Wed=2, Sat=5)
    # ---------------------------------------------------------
    if current_day in [2, 5]:
        cloze_rules = """### JSON SCHEMA & RANDOMISATION RULES
- The "passage" must contain exactly 8 blanks labelled as (1) ______, (2) ______, up to (8) ______.
- Generate exactly 8 questions. The "question" field should just be the blank number, e.g., "Q1. (1) ______".
- Output a flat array of strings for "options". DO NOT use "A.", "B.", "C.", or "D.".
- The root object MUST contain: "instruction": "Directions: In the following passage, there are eight blanks. Choose the most appropriate option for each blank." """

        prompt_cloze = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Create a Cloze Test using the provided coherent text block.
[RULES] {cloze_rules}
[TEXT] 
{cloze_text}
[OUTPUT FORMAT] 
Return EXACTLY this JSON structure:
{{
  "type": "cloze_test",
  "instruction": "Directions: In the following passage, there are eight blanks. Choose the most appropriate option for each blank.",
  "passage": "Economic growth alone does not automatically lead to social progress. For development to be truly (1) ______, its benefits...",
  "questions": [
    {{
      "question": "Q1. (1) ______",
      "options": ["inclusive", "excessive", "temporary", "reluctant"],
      "correct_answer": "inclusive",
      "explanation": "Detailed explanation..."
    }}
  ]
}}"""
        
        final_output["set_e"] = generate_and_validate(prompt_cloze, "Cloze Test", cloze_rules)
        time.sleep(10)

    # ---------------------------------------------------------
    # SET G: WORD USAGE (Tue=1, Wed=2, Fri=4, Sat=5)
    # ---------------------------------------------------------
    if current_day in [1, 2, 4, 5]:
        wu_rules = """### JSON SCHEMA & RANDOMISATION RULES
- Extract 5 challenging words. The "question" field should just be the TARGET WORD in uppercase (e.g., "ABANDON").
- The "options" must be 4 full sentences using the word. DO NOT prepend "A.", "B." to the sentences.
- Only ONE sentence uses the word correctly both grammatically and contextually.
- The root object MUST contain: "instruction": "Directions: Choose the sentence in which the given word is used correctly and appropriately." """

        prompt_wu = f"""[ROLE] Expert Question Setter for SSC CGL Tier-II and Banking PO.
[TASK] Extract 5 challenging words from the text and create Word Usage questions.
[RULES] {wu_rules}
[TEXT] 
{wu_text}
[OUTPUT FORMAT] 
Return EXACTLY this JSON structure:
{{
  "type": "word_usage",
  "instruction": "Directions: Choose the sentence in which the given word is used correctly and appropriately.",
  "questions": [
    {{
      "question": "ABANDON",
      "options": [
        "The company decided to abandon its employees with new training programmes.",
        "He abandoned the idea after discovering that it was impractical.",
        "The teacher abandoned the students to complete the examination carefully.",
        "She abandoned her success because she worked very hard."
      ],
      "correct_answer": "He abandoned the idea after discovering that it was impractical.",
      "explanation": "Abandon means to give up. Sentence 2 is the only logical usage."
    }}
  ]
}}"""
        
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
