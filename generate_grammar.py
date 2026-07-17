import os
import json
import time
import requests
from google import genai
from google.genai import types

# --- 1. SETUP CREDENTIALS ---
KEYS = [
    os.environ.get("GEMINI_KEY_1"),
    os.environ.get("GEMINI_KEY_2"),
    os.environ.get("GEMINI_KEY_3")
]
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

def main():
    print("🚀 Starting Advanced Grammar Generation...")

    # --- 2. LOAD EDITORIALS ---
    try:
        with open('editorials.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        item_1, item_2 = data[0], data[1]
        ed_title_1, ed_title_2 = item_1['title'], item_2['title']
        combined_text = item_1['text'] + " " + item_2['text']

        sentences = [s.strip() + '.' for s in combined_text.split('.') if s.strip()]
        chunks = []
        base_size = len(sentences) // 15
        remainder = len(sentences) % 15
        start_idx = 0
        for i in range(15):
            end_idx = start_idx + base_size + (1 if i < remainder else 0)
            chunks.append(" ".join(sentences[start_idx:end_idx]))
            start_idx = end_idx

        if len(chunks) < 15: 
            chunks = [combined_text] * 15 
    except Exception as e:
        print(f"⚠️ Failed to load or chunk editorials: {e}")
        return

    # --- 3. BULLDOZER LOGIC ---
    master_chunk_idx = 0 

    def generate_with_bulldozer(prompt, target_count):
        nonlocal master_chunk_idx
        successful_mcqs = []

        while len(successful_mcqs) < target_count and master_chunk_idx < 15:
            current_prompt = prompt.replace("{CHUNK_TEXT}", chunks[master_chunk_idx])
            mcq = None
            for attempt in range(len(KEYS)):
                try:
                    if not KEYS[attempt]: continue
                    temp_client = genai.Client(api_key=KEYS[attempt])
                    response = temp_client.models.generate_content(
                        model='gemini-3.5-flash', 
                        contents=current_prompt, 
                        config=types.GenerateContentConfig(temperature=0.7)
                    )
                    mcq = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                    break
                except Exception as e:
                    time.sleep(2)

            if mcq:
                successful_mcqs.append(mcq)
            else:
                print("⚠️ Bulldozer: Gemini failed. Retrying on next chunk...")

            master_chunk_idx += 1
            time.sleep(2)

        return successful_mcqs

    # --- 4. PROMPTS ---
    prompt_A = """You are India's best English question setter for SSC CGL, SSC CHSL, SSC CPO, SSC MTS, IBPS PO, IBPS Clerk, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
Editorial Context:
"{CHUNK_TEXT}"
Create EXACTLY ONE Error Detection question.
Target Grammar Topic: Advanced Grammar

STRICT RULES
1. Difficulty must match actual SSC CGL Tier-II and Banking PO (IBPS/SBI) level.
2. Use natural newspaper-quality English inspired by the editorial context. The sentence should resemble recent SSC CGL Tier-II and Banking PO questions by naturally incorporating subordinate clauses, relative clauses, participial phrases or modifiers where appropriate. Do not increase length unnecessarily.
3. The sentence must contain ONLY ONE grammatical error.
Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
4. After correcting that one error, the complete sentence must become fully correct.
5. Divide the sentence into EXACTLY four parts labelled (A), (B), (C), and (D).
6. The fifth option MUST be "(E) No Error".
7. The incorrect portion must appear in ONLY ONE part.
8. Never create questions with two possible answers.
9. Never test spelling, punctuation or typing mistakes.
10. Focus ONLY on grammatical errors.
13. Explanation must clearly state what is wrong, why it is wrong, and the correct form.
14. Do NOT mention option numbers in the explanation, just the grammatical reason.
15. Return ONLY valid JSON.

TELEGRAM LIMITS
- sentence < 250 characters
- explanation < 190 characters
- every option < 90 characters

Return EXACTLY this JSON structure:
{
    "sentence": "(A) Neither of the two proposals / (B) were considered suitable / (C) for immediate implementation / (D) by the planning committee.",
    "options":[
        "(A) Neither of the two proposals",
        "(B) were considered suitable",
        "(C) for immediate implementation",
        "(D) by the planning committee.",
        "(E) No Error"
    ],
    "correct_answer":"(B) were considered suitable",
    "explanation":"Use 'was' instead of 'were'. 'Neither of' is followed by a plural noun but takes a singular verb."
}"""

    prompt_B = """You are India's best English question setter for SSC CGL Tier-II, SSC CHSL, SSC CPO, IBPS PO, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
Editorial Context:
"{CHUNK_TEXT}"
Create EXACTLY ONE Sentence Improvement question.
Target Grammar Topic: Advanced Grammar

STRICT RULES
1. Difficulty must match recent SSC CGL Tier-II and Banking PO exams.
2. Use natural newspaper-quality English inspired by the editorial context. 
3. The complete sentence must be meaningful and grammatically correct AFTER applying the correct answer.
4. Identify EXACTLY ONE continuous phrase (2-7 words) that needs improvement. Output this exact phrase in the "target_phrase" JSON field. Do NOT use HTML or underlines in the sentence itself.
6. If the original phrase is incorrect: Exactly ONE replacement option must be correct. "No Improvement" must be incorrect.
7. If the original phrase is already correct: The correct answer MUST be "No Improvement".
8. Provide EXACTLY four options. The fourth option MUST always be: "No Improvement".
10. Only ONE option can be correct.
14. Distractors must be realistic and resemble actual SSC/Banking options.
16. Explanation must briefly state why the correct option is right and others are wrong.
17. Return ONLY valid JSON.

TELEGRAM LIMITS
- sentence < 250 characters
- explanation < 190 characters
- every option < 90 characters

Return EXACTLY this JSON:
{
    "target_phrase": "capable to handle",
    "sentence": "The manager is capable to handle difficult situations.",
    "options": [
        "capable of handling",
        "capable for handling",
        "capable in handling",
        "No Improvement"
    ],
    "correct_answer": "capable of handling",
    "explanation": "'Capable' is followed by 'of' and a gerund. Hence 'capable of handling' is correct."
}"""

    prompt_C = """You are India's best English question setter for SSC CGL Tier-II, SSC CHSL, SSC CPO, IBPS PO, IBPS Clerk, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
Editorial Context:
"{CHUNK_TEXT}"
Create EXACTLY ONE Fill-in-the-Blank question.

STRICT RULES
1. Difficulty must match recent SSC and Banking exams.
2. Write a natural newspaper-quality sentence in which the blank(s) cannot be answered correctly without understanding the entire sentence.
3. Leave exactly one blank represented by "______".
4. Provide EXACTLY 4 options. Only ONE option must fit.
6. Every distractor must look highly plausible but become incorrect because of context or grammar.
7. All options must belong to the SAME part of speech.
8. Avoid extremely rare or GRE-level vocabulary.
12. Explanation should briefly include meaning of correct word and why distractors fail.
13. Return ONLY valid JSON.

TELEGRAM LIMITS
- sentence < 250 characters
- explanation < 190 characters
- every option < 90 characters

Return EXACTLY this JSON structure:
{
    "sentence": "The committee reached a ______ decision after hours of discussion.",
    "options": ["unanimous", "temporary", "flexible", "ordinary"],
    "correct_answer": "unanimous",
    "explanation": "Unanimous means fully in agreement. It perfectly fits the context of a decision made by a committee."
}"""

    prompt_C_double = """You are India's best English question setter for SSC CGL Tier-II and Banking PO exams.
Editorial Context:
"{CHUNK_TEXT}"
Create EXACTLY ONE Double Fill-in-the-Blank question.

STRICT RULES
1. Difficulty must match recent SSC and Banking exams.
2. Write a natural newspaper-quality sentence.
3. Leave EXACTLY TWO blanks, each represented by "______". Do not use a single blank.
4. Provide EXACTLY 4 options. Only ONE option must fit both grammatically and contextually.
7. All options must belong to the SAME part of speech.
10. For Double Fillers: both blanks should depend on each other.
12. Explanation should briefly include meaning of correct words and why they fit.
13. Return ONLY valid JSON.

TELEGRAM LIMITS
- sentence < 250 characters
- explanation < 190 characters
- every option < 90 characters

Return EXACTLY this JSON structure:
{
    "custom_ui": "Choose the pair of words that best completes the sentence.",
    "sentence": "The company remained ______ despite the ______ market conditions.",
    "options": ["resilient, adverse", "fragile, favourable", "hesitant, optimistic", "rigid, stable"],
    "correct_answer": "resilient, adverse",
    "explanation": "Resilient means able to withstand shock, and adverse means unfavorable. This pair perfectly contrasts the company's strength against poor conditions."
}"""

    # --- 5. GENERATE & SAVE ---
    print("⚙️ Generating Set A (Error Detection)...")
    set_a = generate_with_bulldozer(prompt_A, 5)
    
    print("⚙️ Generating Set B (Sentence Improvement)...")
    set_b = generate_with_bulldozer(prompt_B, 5)
    
    print("⚙️ Generating Set C (Fillers)...")
    set_c = generate_with_bulldozer(prompt_C, 3) + generate_with_bulldozer(prompt_C_double, 2)

    final_output = {
        "titles": [ed_title_1, ed_title_2],
        "set_a": set_a,
        "set_b": set_b,
        "set_c": set_c
    }

    with open("grammar.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4)
    print("✅ Successfully saved all sets to grammar.json!")

    # --- 6. SEND TELEGRAM PREVIEW ---
    if BOT_TOKEN and ADMIN_CHAT_ID:
        preview_msg = "📝 **DRAFT READY: EXAM TRIALS**\n\n"
        preview_msg += f"✅ Successfully generated **{len(set_a) + len(set_b) + len(set_c)}** advanced grammar questions via GitHub Actions!\n"
        preview_msg += f"🎯 Set A: {len(set_a)} Error Detection\n"
        preview_msg += f"🎯 Set B: {len(set_b)} Sentence Improvement\n"
        preview_msg += f"🎯 Set C: {len(set_c)} Fillers\n\n"
        preview_msg += "🔗 **Check the full drafts here:**\n"
        preview_msg += "[View grammar.json on GitHub](https://github.com/prathu-developer/exam-scraper-api/blob/main/grammar.json)"

        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": preview_msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })

if __name__ == "__main__":
    main()
