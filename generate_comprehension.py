import os
import json
import time
import requests
import random
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup # type: ignore
from readability import Document # type: ignore
from datetime import datetime
from google import genai
from google.genai import types # type: ignore

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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{step}] {details}\n"
    with open("comprehension_audit_log.txt", "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

# --- 2. EXAM CONCEPT BANKS[cite: 9] ---
CONCEPT_BANKS = {
    "RC_Main_Idea": [
        "Central idea of the passage", "Main argument", "Primary theme", "Best summary",
        "Most appropriate title", "Primary purpose", "Overall message", "Dominant concern",
        "Core issue discussed", "Central thesis", "Main conclusion", "Overall perspective",
        "Best description of the passage"
    ],
    "RC_Direct_Factual": [
        "Explicit fact", "Specific detail", "Reason stated by the author", "Event/detail mentioned in passage",
        "Comparison explicitly made", "Example cited by author", "Purpose/function of an example",
        "Cause explicitly stated", "Effect explicitly stated", "Sequence/detail relationship",
        "Who/what/when/where detail", "Statement directly supported by passage",
        "Statement directly contradicted by passage", "Which statement is true according to passage",
        "Which statement is NOT true according to passage"
    ],
    "RC_Inference": [
        "What can be inferred", "What cannot be inferred", "Logical implication", "Implied conclusion",
        "Author's implied view", "Supported inference", "Indirect conclusion", "Logical consequence",
        "Likely outcome", "Reasonable assumption", "Underlying assumption", "Implied relationship",
        "Deduction from two separate passage facts", "Conclusion based on combined evidence",
        "Situation that logically follows from the passage"
    ],
    "RC_Tone_Purpose": [
        "Author's purpose", "Author's intention", "Tone", "Attitude toward the subject", "Overall stance",
        "Positive/negative/neutral attitude", "Critical tone", "Cautious tone", "Sceptical tone",
        "Analytical tone", "Persuasive tone", "Concerned tone", "Optimistic/pessimistic tone",
        "Approving/disapproving tone", "Objective/explanatory tone", "Purpose of presenting a particular argument/example"
    ],
    "RC_Vocab_Phrase": [
        "Meaning of a word as used in passage", "Closest contextual meaning", "Meaning of a phrase",
        "Meaning of an expression", "Contextual synonym", "Contextual antonym", "Figurative meaning",
        "Literal vs contextual meaning", "Reference of a highlighted expression", "Meaning of an idiomatic expression",
        "Meaning of a phrasal verb", "Context-dependent word sense"
    ],
    "RC_Application_Reasoning": [
        "Main argument", "Supporting argument", "Author's reasoning", "Evidence used to support a claim",
        "Claim–evidence relationship", "Cause–effect reasoning", "Problem–solution reasoning",
        "Comparison/contrast reasoning", "Counterargument", "Rebuttal", "Assumption behind an argument",
        "Strengthening a passage-based argument", "Weakening a passage-based argument", "Why the author mentions a particular point",
        "Relationship between two arguments", "Function of a paragraph/section", "Likely consequence",
        "What would happen if a condition changed", "Passage-based application", "Applying author's reasoning to a new situation",
        "Best predicted outcome", "Policy/action implied by passage", "Situation consistent with passage",
        "Situation inconsistent with passage", "Logical extension of author's argument"
    ],
    "PJ_Structures": [
        "General -> specific", "Specific -> generalisation", "Problem -> cause -> consequence", "Problem -> solution",
        "Problem -> consequence -> solution", "Cause -> effect", "Effect -> cause", "Claim -> explanation",
        "Claim -> evidence", "Claim -> example", "Example -> conclusion", "Statement -> elaboration",
        "Idea -> illustration", "Contrast", "Chronology", "Before -> change -> after", "Situation -> development -> result",
        "Question -> answer", "Observation -> explanation", "Theory -> application", "Old situation -> new situation",
        "Issue -> response -> outcome", "Argument -> counterargument -> conclusion"
    ],
    "PJ_Linking_Devices": [
        "Pronoun reference", "Demonstrative reference", "Repeated key noun", "Synonym chain", "Lexical repetition",
        "Contrast markers", "Cause/effect markers", "Result markers", "Addition markers", "Example markers",
        "Chronological markers", "Conditional markers", "Concession markers", "Concluding markers",
        "Definite article / prior reference", "General statement followed by explanation", "Definition followed by application",
        "Question followed by answer"
    ],
    "Cloze_Reasoning": [
        "Contextual vocabulary", "Contextual synonym", "Contextual antonym", "Word-choice distinction", "Shades of meaning",
        "Verb–noun collocation", "Adjective–noun collocation", "Adverb–verb collocation", "Common editorial collocation",
        "Fixed expression", "Idiomatic usage", "Phrasal verb", "Verb form", "Tense", "Subject–verb agreement", "Article",
        "Determiner", "Pronoun", "Preposition", "Conjunction", "Modal", "Parallel construction", "Cause", "Effect",
        "Contrast", "Concession", "Addition", "Example", "Result", "Condition", "Purpose", "Sequence", "Continuation", "Conclusion",
        "Immediate sentence context", "Previous sentence dependency", "Following sentence dependency", "Paragraph-level dependency",
        "Long-range contextual dependency"
    ],
    "WU_Traps": [
        "Wrong semantic sense", "Wrong collocation", "Wrong preposition", "Wrong transitivity", "Wrong grammatical category",
        "Wrong complement pattern", "Wrong register", "Wrong idiomatic usage", "Wrong literal/figurative sense",
        "Confused near-synonym", "Incorrect subject compatibility", "Incorrect object compatibility", "Incorrect verb pattern",
        "Incorrect noun/adjective relationship", "Contextually inappropriate but grammatically correct usage"
    ]
}

# --- 3. PERSISTENT NOVELTY MEMORY SYSTEM[cite: 9] ---
MEMORY_FILE = "comprehension_memory.json"
RECENT_CONTENT_LIMIT = 40

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rc_concepts": [],
        "pj_concepts": [],
        "cloze_concepts": [],
        "wu_concepts": [],
        "wu_words": []
    }

global_memory = load_memory()

def save_memory():
    for key in global_memory:
        if len(global_memory[key]) > RECENT_CONTENT_LIMIT:
            global_memory[key] = global_memory[key][-RECENT_CONTENT_LIMIT:]
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(global_memory, f, indent=4)
    except Exception as e:
        log_audit("MEMORY_ERROR", f"Failed to save memory: {e}")

def remember_content(category, record):
    record["date_used"] = datetime.now().strftime("%Y-%m-%d")
    global_memory.setdefault(category, []).append(record)

def was_recently_used(category, key_name, value):
    for item in global_memory.get(category, []):
        if item.get(key_name) == value:
            return True
    return False

def select_novel_concept(category, key_name, pool):
    """Selects a novel concept avoiding recent memory[cite: 9]."""
    available = [x for x in pool if not was_recently_used(category, key_name, x)]
    if not available:
        available = pool # Fallback
    choice = random.choice(available)
    return choice

# --- 4. SCRAPING ENGINE ---
def scrape_reader_mode(url):
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

# --- 5. DETERMINISTIC PYTHON VALIDATOR ---
def python_deterministic_validator(set_name, data, expected_q_count):
    if not isinstance(data, dict): return False, "Root element is not a JSON object."
    if "questions" not in data or not isinstance(data["questions"], list): return False, "Missing or invalid 'questions' array."
    
    questions = data["questions"]
    if len(questions) != expected_q_count: return False, f"Expected exactly {expected_q_count} questions, got {len(questions)}."

    forbidden_exp_terms = ["option a", "option b", "option c", "option d", "first option", "second option", "third option", "fourth option", "option 1", "option 2", "option 3", "option 4"]
    alphabet_prefix_pattern = re.compile(r"^[\(]?[A-D][\)\.]\s", re.IGNORECASE)

    for i, q in enumerate(questions):
        if "options" not in q or len(q["options"]) != 4: return False, f"Question {i+1} does not have exactly 4 options."
        if len(set(q["options"])) != 4: return False, f"Question {i+1} has duplicate options."
        if "correct_answer" not in q or q["correct_answer"] not in q["options"]: return False, f"Question {i+1} correct_answer does not exactly match an option."
            
        for opt in q["options"]:
            if alphabet_prefix_pattern.match(opt): return False, f"Question {i+1} contains forbidden A/B/C/D prefixes in options."
                
        explanation = q.get("explanation", "").lower()
        if any(term in explanation for term in forbidden_exp_terms): return False, f"Question {i+1} explanation references an option by its physical position or letter."

    if set_name == "Cloze Test":
        passage = data.get("passage", "")
        for i in range(1, 9):
            marker = f"({i})"
            if passage.count(marker) != 1: return False, f"Cloze passage must contain EXACTLY ONE instance of {marker}."
        for i, q in enumerate(questions):
            q_text = q.get("question", "")
            if f"Q{i+1}." not in q_text and f"({i+1})" not in q_text: return False, f"Question {i+1} text must map clearly to blank ({i+1})."

    if set_name == "Para Jumbles":
        if "correct_sequence" not in data or not isinstance(data["correct_sequence"], list): return False, "Missing or invalid 'correct_sequence'."
        seq = data["correct_sequence"]
        if sorted(seq) != ["A", "B", "C", "D", "E", "F"]: return False, "correct_sequence must contain exactly elements A, B, C, D, E, F exactly once."
        if "fixed_sentence" not in data or "fixed_position" not in data: return False, "Must provide 'fixed_sentence' (A-F) and 'fixed_position' (1-6) fields."
        
        fixed_s = data["fixed_sentence"]
        fixed_p = int(data["fixed_position"])
        if not (1 <= fixed_p <= 6): return False, "fixed_position must be between 1 and 6."
        if seq[fixed_p - 1] != fixed_s: return False, f"Declared fixed sentence {fixed_s} at position {fixed_p} does not match correct_sequence {seq}."

        for i, q in enumerate(questions):
            if "sentences" not in q or sorted(q["sentences"].keys()) != ["A", "B", "C", "D", "E", "F"]: return False, f"Question {i+1} missing EXACT 6 sentences A-F."
            for opt in q["options"]:
                if not any(char in ["A", "B", "C", "D", "E", "F"] for char in opt): return False, f"Para Jumble option '{opt}' is invalid. Must contain valid sentence labels."

    if set_name == "Word Usage":
        for i, q in enumerate(questions):
            w = q.get("question", "").strip().upper()
            if was_recently_used("wu_words", "target_word", w): return False, f"Word '{w}' was recently used in a previous exam. Generate a different word."

    return True, "Passed deterministic validation."

# --- 6. AI ENGINE & PIPELINE ---
def call_gemini_raw(prompt, step_name):
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
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg: continue
                    elif "503" in error_msg or "unavailable" in error_msg: time.sleep(30); continue
                    else: time.sleep(5)
    raise Exception(f"🚨 Failed during {step_name} after all retries.")

def generate_and_validate(generation_prompt, set_name, validation_rules, expected_q_count, max_refinements=3):
    raw_json = call_gemini_raw(generation_prompt, f"{set_name} - Generation")
    
    for attempt in range(max_refinements):
        is_valid_python, python_reason = python_deterministic_validator(set_name, raw_json, expected_q_count)
        
        val_prompt = f"""[ROLE] Elite QA Reviewer for SSC CGL.
[TASK] Review this JSON against the structural rules. 
[CRITICAL] Explanations MUST NOT mention option positions (e.g., "Option A"). Options MUST NOT have A/B/C/D prefixes.
[RULES] {validation_rules}
[INPUT JSON] {json.dumps(raw_json)}
[OUTPUT] Return ONLY valid JSON. If perfect: {{"status": "PASS"}}. If flawed: {{"status": "FAIL", "reasons": {{"q_num": "reason"}}}}."""
        
        ai_val_result = call_gemini_raw(val_prompt, f"{set_name} - AI Validation (Attempt {attempt+1})")
        is_valid_ai = ai_val_result.get("status") == "PASS"

        if is_valid_python and is_valid_ai:
            log_audit("QA_PASS", f"{set_name} passed both Python and AI QA perfectly.")
            return raw_json
            
        combined_reasons = {}
        if not is_valid_python: combined_reasons["deterministic_python_error"] = python_reason
        if not is_valid_ai: combined_reasons.update(ai_val_result.get("reasons", {}))

        log_audit("QA_FAIL", f"{set_name} failed QA. Initiating regeneration... Reasons: {combined_reasons}")
        
        refine_prompt = f"""[ROLE] Senior Question Setter correcting flawed questions.
[TASK] The JSON failed QA. Fix ONLY the options, questions, or explanations that failed. 
[FAILURE REASONS] {json.dumps(combined_reasons)}
[INPUT JSON] {json.dumps(raw_json)}
[OUTPUT] Return ONLY the FULL, corrected JSON object."""
        
        raw_json = call_gemini_raw(refine_prompt, f"{set_name} - Regeneration (Attempt {attempt+1})")
    
    is_valid_python, python_reason = python_deterministic_validator(set_name, raw_json, expected_q_count)
    if not is_valid_python:
        log_audit("QA_FATAL", f"🚨 {set_name} failed final Python QA ({python_reason}). Set safely dropped to protect exam integrity.")
        return None
        
    return raw_json

def prepare_exam_materials(ed1_text, ed2_text):
    prompt = f"""[ROLE] Chief Content Editor
[TASK] Analyze two editorials and route them.
[RULES]
1. Select the BEST editorial for Reading Comprehension (RC). Extract a coherent, continuous passage of 500-800 words. Keep exact original wording.
2. CLOZE PASSAGE: Using the OTHER editorial, extract a continuous section of 180-250 words.
3. PARA JUMBLE INSPIRATION: Use the remaining text of the OTHER editorial.
[ED1] {ed1_text}
[ED2] {ed2_text}
[OUTPUT FORMAT] JSON strictly matching:
{{"rc_editorial_id": 1, "rc_passage": "...", "cloze_editorial_id": 2, "cloze_passage": "...", "pj_inspiration_text": "...", "wu_source_text": "..."}}"""
    return call_gemini_raw(prompt, "Material Prep & Routing")

def main():
    log_audit("START", "🚀 Initializing Advanced Comprehension Pipeline with Concept Bank Architecture...")
    current_day = 0 # 🟢 TEMPORARY TEST OVERRIDE: Forcing Monday!
    # if current_day == 6: return  # 🟢 Commented out so it doesn't block us!

    editorials = get_hindu_editorials()
    materials = prepare_exam_materials(editorials[0]['text'], editorials[1]['text'])
    
    final_output = {"date": datetime.now().strftime("%Y-%m-%d")}

    # ---------------------------------------------------------
    # SET D: READING COMPREHENSION (Mon=0, Thu=3)
    # ---------------------------------------------------------
    if current_day in [0, 3]:
        # Novelty: Rotate internal subtypes using the Concept Bank[cite: 9]
        concept_1 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Main_Idea"])
        concept_2 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Inference"])
        concept_3 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Direct_Factual"])
        concept_4 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Tone_Purpose"])
        concept_5 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Vocab_Phrase"])
        concept_6 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Direct_Factual"])
        concept_7 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Inference"] + CONCEPT_BANKS["RC_Application_Reasoning"])
        concept_8 = select_novel_concept("rc_concepts", "concept", CONCEPT_BANKS["RC_Vocab_Phrase"])

        rc_blueprint = [
            f"1. Main Idea / Central Theme: Focus on '{concept_1}'",
            f"2. Inference: Focus on '{concept_2}'",
            f"3. Direct / Factual: Focus on '{concept_3}'",
            f"4. Tone / Author's Purpose: Focus on '{concept_4}'",
            f"5. Vocabulary / Phrase in Context: Focus on '{concept_5}'",
            f"6. Direct / Factual: Focus on '{concept_6}'",
            f"7. Inference / Logical Consequence: Focus on '{concept_7}'",
            f"8. Vocabulary / Phrase in Context: Focus on '{concept_8}'"
        ]

        rc_rules = f"""### EXAM CONCEPT SELECTION & BLUEPRINT
Strictly adhere to this specific distribution: {json.dumps(rc_blueprint)}. 
Create conceptually fresh distractors and reasoning logic corresponding EXACTLY to the requested concepts.

### JSON SCHEMA & RANDOMISATION RULES
- Flat array for "options". NO "A.", "B.", "C." prefixes.
- "correct_answer" must exactly match the correct option string.
- Explanation must rely purely on passage logic, never mentioning option position.
- Output EXACTLY 8 questions.

### VALIDATION & GROUNDING RULES
- SOURCE-BOUND: Every question, correct option, and explanation MUST be supported ONLY by the supplied passage. No outside knowledge.
- ANTI-ELIMINATION: At least 2 distractors per question must require actual reading/reasoning to eliminate.
- EVIDENCE VALIDATION: Exact passage evidence must logically support the correct answer and explanation.
- PREVENT WORDING CLUES: Correct options must not be obviously longer or more precise than distractors."""

        prompt_rc = f"""[ROLE] Expert Question Setter.
[TASK] Create an 8-question RC test.
[RULES] {rc_rules}
[PASSAGE] {materials.get('rc_passage')}
[OUTPUT FORMAT] JSON: {{"type": "reading_comprehension", "instruction": "Directions: Read the following passage carefully and answer the questions given below.", "passage": "...", "questions": [{{ "question": "...", "options": ["...", "..."], "correct_answer": "...", "explanation": "..."}}]}}"""
        
        result = generate_and_validate(prompt_rc, "Reading Comprehension", rc_rules, 8)
        if result: 
            final_output["set_d"] = result
            remember_content("rc_concepts", {"section": "RC", "slot": 2, "concept": concept_2})
            remember_content("rc_concepts", {"section": "RC", "slot": 4, "concept": concept_4})
            remember_content("rc_concepts", {"section": "RC", "slot": 7, "concept": concept_7})
        time.sleep(10)

    # ---------------------------------------------------------
    # SET F: PARA JUMBLES (Tue=1, Fri=4)
    # ---------------------------------------------------------
    if current_day in [1, 4]:
        # Novelty: Rotate internal PJ structures and devices[cite: 9]
        pj_struct = select_novel_concept("pj_concepts", "concept", CONCEPT_BANKS["PJ_Structures"])
        pj_device = select_novel_concept("pj_concepts", "concept", CONCEPT_BANKS["PJ_Linking_Devices"])

        dynamic_fixed_label = random.choice(["A", "B", "C", "D", "E", "F"])
        dynamic_fixed_pos = random.randint(1, 6)

        pj_rules = f"""### EXAM CONCEPT SELECTION
- Target paragraph structure: {pj_struct}.
- Incorporate this specific logical linking device to connect sentences: {pj_struct}.

### JSON SCHEMA & LOGIC RULES
- Write a coherent 6-sentence paragraph based on the inspiration text. 
- Generate the "correct_sequence" array (e.g. ["C","F","A","D","B","E"]) showing the final logical order.
- CRITICAL DYNAMIC ASSIGNMENT: You MUST assign Sentence {dynamic_fixed_label} to occupy position {dynamic_fixed_pos} in your correct_sequence.
- The "instruction" must dynamically declare this. Example: "Directions: In the following question, six sentences are given. Sentence {dynamic_fixed_label} is fixed as the {dynamic_fixed_pos} sentence in the paragraph. The remaining five..."
- Include the "sentences" dictionary (A through F) inside EVERY question object.
- Generate EXACTLY 5 questions based on the sequence (e.g., "Which sentence comes before B?", "Which is the last sentence?").
- Options must be flat strings like "A", "B", or sequence strings "D-F-B-E". NO "A. Option" prefixes.
- Only ONE defensible correct sequence."""

        prompt_pj = f"""[ROLE] Expert Question Setter.
[TASK] Create 5 Para Jumble questions based on 1 fixed paragraph.
[RULES] {pj_rules}
[SOURCE THEME] {materials.get('pj_inspiration_text')}
[OUTPUT FORMAT] JSON: {{"type": "para_jumbles", "instruction": "...", "fixed_sentence": "{dynamic_fixed_label}", "fixed_position": {dynamic_fixed_pos}, "correct_sequence": [], "questions": [{{ "sentences": {{"A": "...", "B": "..."}}, "question": "Which sentence should come immediately after Sentence X?", "options": ["B", "C", "D", "E"], "correct_answer": "C", "explanation": "..."}}]}}"""
        
        result = generate_and_validate(prompt_pj, "Para Jumbles", pj_rules, 5)
        if result: 
            final_output["set_f"] = result
            remember_content("pj_concepts", {"section": "PJ", "concept": pj_struct})
            remember_content("pj_concepts", {"section": "PJ", "concept": pj_device})
        time.sleep(10)

    # ---------------------------------------------------------
    # SET E: CLOZE TEST (Wed=2, Sat=5)
    # ---------------------------------------------------------
    if current_day in [2, 5]:
        # Novelty: Build a balanced 8-concept layout[cite: 9]
        cloze_layout = random.sample(CONCEPT_BANKS["Cloze_Reasoning"], 8)

        cloze_rules = f"""### EXAM CONCEPT SELECTION
- The 8 blanks must test these exact concepts in order: {json.dumps(cloze_layout)}. Do NOT make every blank a vocabulary test.

### JSON SCHEMA & LOGIC RULES
- Passage must contain exactly 8 blanks labelled (1), (2)... (8). Each must appear exactly once.
- Output exactly 8 questions. Question text must just be: "Q1. (1) ______".
- Do NOT create eight independent filler questions. The surrounding context must be strictly required to determine the answer.
- Flat array for "options". NO "A.", "B.", "C." prefixes.
- Explanation must rely purely on contextual logic, never mentioning option position.
- Distractors must be grammatically plausible (unless grammar is the exact skill tested). No absurd options."""

        prompt_cloze = f"""[ROLE] Expert Question Setter.
[TASK] Create a Cloze Test using the text.
[RULES] {cloze_rules}
[TEXT] {materials.get('cloze_passage')}
[OUTPUT FORMAT] JSON: {{"type": "cloze_test", "instruction": "Directions: In the following passage, there are eight blanks...", "passage": "...", "questions": [{{ "question": "Q1. (1) ______", "options": ["...", "..."], "correct_answer": "...", "explanation": "..."}}]}}"""
        
        result = generate_and_validate(prompt_cloze, "Cloze Test", cloze_rules, 8)
        if result: 
            final_output["set_e"] = result
            for concept in cloze_layout:
                remember_content("cloze_concepts", {"section": "Cloze", "concept": concept})
        time.sleep(10)

    # ---------------------------------------------------------
    # SET G: WORD USAGE (Tue=1, Wed=2, Fri=4, Sat=5)
    # ---------------------------------------------------------
    if current_day in [1, 2, 4, 5]:
        # Novelty: Rotate 5 different traps[cite: 9]
        wu_layout = random.sample(CONCEPT_BANKS["WU_Traps"], 5)
        
        wu_rules = f"""### EXAM CONCEPT SELECTION
- Extract 5 challenging words. For EACH word, build the distractors based on the corresponding trap from this list: {json.dumps(wu_layout)}.

### JSON SCHEMA & LOGIC RULES
- Question text is just the TARGET WORD.
- "options" are 4 full sentences using the word. NO "A.", "B." prefixes.
- Exactly ONE sentence uses the word correctly in BOTH grammar and contextual meaning.
- ALL 4 options must be grammatically natural. Incorrect options must fail due to improper contextual meaning, poor collocation, or incorrect prepositions, NOT obvious grammar mistakes."""

        prompt_wu = f"""[ROLE] Expert Question Setter.
[TASK] Extract 5 novel words and create Word Usage questions.
[RULES] {wu_rules}
[TEXT] {materials.get('wu_source_text')}
[OUTPUT FORMAT] JSON: {{"type": "word_usage", "instruction": "Directions: Choose the sentence in which the given word is used correctly...", "questions": [{{ "question": "ABANDON", "options": ["Sentence 1...", "Sentence 2..."], "correct_answer": "...", "explanation": "..."}}]}}"""
        
        result = generate_and_validate(prompt_wu, "Word Usage", wu_rules, 5)
        if result: 
            final_output["set_g"] = result
            for i, q in enumerate(result["questions"]):
                remember_content("wu_words", {"section": "WU", "target_word": q["question"].strip().upper()})
                remember_content("wu_concepts", {"section": "WU", "concept": wu_layout[i]})

    # --- 6. SAVE FINAL OUTPUT & MEMORY ---
    if len(final_output) > 1:
        with open("comprehension_tests.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4)
        save_memory() # Commit the new history
        log_audit("COMPLETE", "🎉 Finished! QA-validated sets saved, and novelty memory committed.")
    else:
        log_audit("COMPLETE", "No valid tests generated for today.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID, "text": f"🚨 **CRITICAL ERROR:**\n`{e}`", "parse_mode": "Markdown"
            })