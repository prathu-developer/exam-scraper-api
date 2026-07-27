import os
import json
import time
import requests
from datetime import datetime
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

def log_audit(step, details):
    """Writes the step-by-step process to the audit log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{step}] {details}\n"
    with open("grammar_audit_log.txt", "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

def main():
    log_audit("START", "🚀 Initializing Advanced Grammar Generation Script...")

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
            
        log_audit("DATA_READY", f"Successfully loaded '{ed_title_1}' & '{ed_title_2}'. Splitting into {len(chunks)} text chunks.")
        
    except Exception as e:
        log_audit("FATAL_ERROR", f"Failed to load or chunk editorials: {e}")
        raise e  # ✨ We raise the error instead of returning so the safety net catches it!

    # --- 3. BULLDOZER LOGIC ---
    master_chunk_idx = 0 

    def generate_with_bulldozer(prompt, target_count, set_name, topic_offset=0):
        nonlocal master_chunk_idx
        successful_mcqs = []

        log_audit("PROCESS", f"Starting {set_name} generation. Target: {target_count} questions.")

        while len(successful_mcqs) < target_count and master_chunk_idx < 15:
            grammar_topics = [
                "Subject Verb Agreement",
                "Tenses",
                "Articles",
                "Prepositions",
                "Pronouns",
                "Determiners",
                "Conjunctions",
                "Parallelism",
                "Comparisons",
                "Infinitive vs Gerund",
                "Participles",
                "Modifier Placement",
                "Relative Pronouns",
                "Relative Clauses",
                "Conditionals",
                "Modals",
                "Sequence of Tenses",
                "Fixed Expressions"
            ]
            
            error_parts = [
                "C","A","D","B",
                "A","D","B","C",
                "B","C","A","D",
                "D","B","C","A"
            ]
            # Changes automatically every day
            day_offset = datetime.now().timetuple().tm_yday % len(grammar_topics)

            topic = grammar_topics[
                (master_chunk_idx + day_offset + topic_offset) % len(grammar_topics)
            ]
            error_part = error_parts[master_chunk_idx % len(error_parts)]
            
            log_audit(
                "PROMPT",
                f"[{set_name}] Attempting Q{len(successful_mcqs)+1}/{target_count} | "
                f"Chunk: {master_chunk_idx+1}/15 | Topic: {topic} | Error Part: {error_part}"
            )
            
            current_prompt = (
                prompt
                .replace("{CHUNK_TEXT}", chunks[master_chunk_idx])
                .replace("{GRAMMAR_TOPIC}", topic)
                .replace("{ERROR_PART}", error_part)
            )
            
            mcq = None
            max_chunk_retries = 3
            
            for retry_attempt in range(max_chunk_retries):
                if mcq: 
                    break # Break out if we successfully got a question!
                
                for attempt in range(len(KEYS)):
                    try:
                        if not KEYS[attempt]: continue
                        temp_client = genai.Client(api_key=KEYS[attempt])
                        
                        response = temp_client.models.generate_content(
                            model='gemini-3.6-flash', 
                            contents=current_prompt, 
                            config=types.GenerateContentConfig(temperature=0.7)
                        )
                        
                        # Parse the JSON first
                        parsed_mcq = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                        
                        # --- NEW VALIDATION CHECK ---
                        # If we are generating Fillers (Set C), ensure the blank actually exists
                        if "Set C" in set_name and "______" not in parsed_mcq.get("sentence", ""):
                            raise ValueError("AI failed to include the '______' blank in the sentence.")
                        
                        # If validation passes, assign it to mcq and break the loop
                        mcq = parsed_mcq
                        break # Break out of the key-rotation loop on success
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        if "429" in error_msg or "quota" in error_msg:
                            log_audit("API_WARN", f"[{set_name}] Key {attempt+1} exhausted. Rotating...")
                            continue
                            
                        elif "503" in error_msg or "unavailable" in error_msg:
                            log_audit("API_WARN", f"[{set_name}] 503 Overload on Key {attempt+1}. Waiting 30s...")
                            time.sleep(30)
                            continue
                            
                        else:
                            log_audit("API_WARN", f"[{set_name}] Unknown error on Key {attempt+1}: {error_msg[:40]}...")
                            time.sleep(5)

            if mcq:
                log_audit("SUCCESS", f"[{set_name}] Successfully parsed JSON for Q{len(successful_mcqs)+1}.")
                successful_mcqs.append(mcq)
            else:
                log_audit("SKIP_CHUNK", f"[{set_name}] Exhausted all keys. Chunk {master_chunk_idx+1} failed. Moving to next chunk.")

            master_chunk_idx += 1
            time.sleep(15) # <-- CHANGED FROM 2 TO 15

        return successful_mcqs

    # --- 4. PROMPTS ---
    prompt_A = """
        You are India's best English question setter for SSC CGL, SSC CHSL, SSC CPO, SSC MTS, IBPS PO, IBPS Clerk, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
        Editorial Context:
        "{CHUNK_TEXT}"
        Create EXACTLY ONE Error Detection question.

        The grammatical error must arise naturally from the editorial context.
        Do NOT invent textbook-style sentences.
        Prefer transforming or combining ideas from the editorial into a new sentence instead of copying it.
        Target Grammar Topic:
        {GRAMMAR_TOPIC}
        
        Generate the question ONLY from {GRAMMAR_TOPIC}.

        The grammatical error MUST primarily test this topic.
        Do NOT convert it into a Subject-Verb Agreement question unless {GRAMMAR_TOPIC} itself is Subject-Verb Agreement.
        
        If {GRAMMAR_TOPIC} is Preposition, the error must be a preposition.
        If {GRAMMAR_TOPIC} is Article, the error must be an article.
        If {GRAMMAR_TOPIC} is Parallelism, the error must be parallelism.
        If {GRAMMAR_TOPIC} is Modifier Placement, the error must be modifier placement.
        
        Never replace the requested topic with an easier grammar topic.

        STRICT RULES
        1. Difficulty must match actual SSC CGL Tier-II and Banking PO (IBPS/SBI) level.
        2. Use natural newspaper-quality English inspired by the editorial context. 
        The sentence should resemble recent SSC CGL Tier-II and Banking PO questions by naturally incorporating subordinate clauses, relative clauses, participial phrases or modifiers where appropriate. Do not increase length unnecessarily.
        3. The sentence must contain ONLY ONE grammatical error.
        Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
        4. After correcting that one error, the complete sentence must become fully correct.
        5. Divide the sentence into EXACTLY four parts labelled (A), (B), (C), and (D).
        6. The fifth option MUST be "(E) No Error".
        7. The incorrect portion must appear ONLY in part ({ERROR_PART}).
        The remaining three parts must be completely correct.
        The error must be naturally embedded inside the sentence, not isolated as an obvious incorrect phrase. 
        Avoid errors that can be identified by reading only one option.
        The candidate should usually need to read the complete sentence before locating the error.
        Distribute errors naturally across:
        - subject phrase
        - verb phrase
        - object phrase
        - modifier
        - participial phrase
        - relative clause
        - prepositional phrase
        Do NOT always place the error in the main verb or an easily recognizable idiom.
        8. Never create questions with two possible answers.
        9. Never test spelling, punctuation or typing mistakes.
        11. Avoid extremely rare grammar rules.
        12. The error MUST belong to a standard competitive exam grammar topic.
        13. Explanation must clearly state:
        - what is wrong
        - why it is wrong
        - the correct form
        14. Do NOT mention option numbers in the explanation, just the grammatical reason.
        15. Before returning, verify:
        • Exactly one answer is correct.
        • The assigned grammar topic is actually being tested.
        • The error appears only in ({ERROR_PART}).
        • The error is not visually obvious.
        • The question resembles an actual SSC/IBPS previous-year paper.

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
        }
        """

    prompt_B = """
        You are India's best English question setter for SSC CGL Tier-II, SSC CHSL, SSC CPO, IBPS PO, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
        Editorial Context:
        "{CHUNK_TEXT}"

        Create EXACTLY ONE Sentence Improvement question.

        Target Grammar Topic:
        {GRAMMAR_TOPIC}
        
        The primary grammatical improvement must test {GRAMMAR_TOPIC}.
        Supporting grammar may appear naturally, but the corrected phrase should mainly assess this topic.

        STRICT RULES
        1. Difficulty must match recent SSC CGL Tier-II and Banking PO exams.
        2. Use natural newspaper-quality English inspired by the editorial context. 
        The sentence should resemble recent SSC CGL Tier-II and Banking PO questions by naturally incorporating subordinate clauses, relative clauses, participial phrases or modifiers where appropriate. Do not increase length unnecessarily.
        Do NOT create artificial or textbook sentences.
        Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
        3. The complete sentence must be meaningful and grammatically correct AFTER applying the correct answer.
        4. Identify EXACTLY ONE continuous phrase (2-7 words) that needs improvement. Output this exact phrase in the "target_phrase" JSON field. Do NOT use HTML or underlines in the sentence itself.
        6. If the original phrase is incorrect:
           - Exactly ONE replacement option must be correct.
           - "No Improvement" must be incorrect.
        7. If the original phrase is already correct:
           - The correct answer MUST be "No Improvement".
           - Every replacement option must introduce a grammatical error.
        8. Provide EXACTLY four options.
        9. The fourth option MUST always be:
        "No Improvement"
        10. Only ONE option can be correct.
        11. Focus ONLY on standard competitive exam grammar rules.
        12. Prefer grammar topics commonly tested in SSC and Banking:
        - Subject Verb Agreement
        - Tenses
        - Articles
        - Determiners
        - Pronouns
        - Modals
        - Prepositions
        - Conjunctions
        - Parallelism
        - Comparisons
        - Degrees
        - Infinitive vs Gerund
        - Participles
        - Relative Pronouns
        - Relative Clauses
        - Conditionals
        - Sequence of Tenses
        - Modifier Placement
        - Fixed Expressions
        - Idiomatic Grammar
        - Redundancy

        13. Do NOT test:
        - spelling
        - punctuation
        - capitalization
        - vocabulary meaning
        - style preferences

        14. Distractors must be realistic and resemble actual SSC/Banking options.
        15. Never allow more than one grammatically acceptable answer.
        16. Explanation must briefly state:
        - why the correct option is right
        - why the original or remaining options are wrong

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
        }
        """

    prompt_C = """
        You are India's best English question setter for SSC CGL Tier-II, SSC CHSL, SSC CPO, IBPS PO, IBPS Clerk, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.

        Editorial Context:
        "{CHUNK_TEXT}"

        Create EXACTLY ONE Fill-in-the-Blank question.

        STRICT RULES

        1. Difficulty must match recent SSC and Banking exams.
        2. Write a natural newspaper-quality sentence in which the blank(s) cannot be answered correctly without understanding the entire sentence.
        Do NOT generate artificial or textbook sentences.
        Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
        3. Leave exactly one or two blanks represented by "______".
        4. Provide EXACTLY 4 options.
        5. Only ONE option must fit both grammatically and contextually.
        6. Every distractor must look highly plausible but become incorrect because of context, grammar, collocation or meaning.
        7. All options must belong to the SAME part of speech.
        Example:
        - all nouns
        - all adjectives
        - all verbs
        - all adverbs

        8. Avoid extremely rare or GRE-level vocabulary.
        Prefer advanced but exam-relevant words commonly seen in editorials and SSC/Banking exams.

        9. Frequently test:
        - contextual vocabulary
        - collocations
        - phrasal verbs (when suitable)
        - fixed expressions
        - word usage
        - shades of meaning

        10. For Double Fillers:
        - both blanks should depend on each other.
        - eliminate options through overall sentence meaning rather than one blank alone.
        - avoid independent blanks.

        11. Never allow two options that can both fit.

        12. Explanation should briefly include:
        - meaning of the correct word(s)
        - why they fit
        - why the distractors fail

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
        }
        """

    prompt_C_double = """
        You are India's best English question setter for SSC CGL Tier-II and Banking PO exams.
        Editorial Context:
        "{CHUNK_TEXT}"

        Create EXACTLY ONE Double Fill-in-the-Blank question.

        STRICT RULES
        1. Difficulty must match recent SSC and Banking exams.
        2. Write a natural newspaper-quality sentence in which the blank(s) cannot be answered correctly without understanding the entire sentence.
        Do NOT generate artificial or textbook sentences.
        Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
        3. Leave EXACTLY TWO blanks, each represented by "______". Do not use a single blank.
        4. Provide EXACTLY 4 options.
        5. Only ONE option must fit both grammatically and contextually.
        6. Every distractor must look highly plausible but become incorrect because of context, grammar, collocation or meaning.
        7. All options must belong to the SAME part of speech.
        Example:
        - all nouns
        - all adjectives
        - all verbs
        - all adverbs

        8. Avoid extremely rare or GRE-level vocabulary.
        Prefer advanced but exam-relevant words commonly seen in editorials and SSC/Banking exams.

        9. Frequently test:
        - contextual vocabulary
        - collocations
        - phrasal verbs (when suitable)
        - fixed expressions
        - word usage
        - shades of meaning

        10. For Double Fillers:
        - both blanks should depend on each other.
        - eliminate options through overall sentence meaning rather than one blank alone.
        - avoid independent blanks.

        11. Never allow two options that can both fit.

        12. Explanation should briefly include:
        - meaning of the correct word(s)
        - why they fit
        - why the distractors fail

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
        }
        """

    # --- 5. GENERATE & SAVE ---
        set_a = generate_with_bulldozer(
            prompt_A,
            5,
            "Set A (Error Detection)",
            topic_offset=0
        )
        
        set_b = generate_with_bulldozer(
            prompt_B,
            5,
            "Set B (Sentence Improvement)",
            topic_offset=9
        )
        
        set_c = generate_with_bulldozer(
            prompt_C,
            3,
            "Set C (Single Fillers)"
        ) + generate_with_bulldozer(
            prompt_C_double,
            2,
            "Set C (Double Fillers)"
        )

    final_output = {
        "titles": [ed_title_1, ed_title_2],
        "set_a": set_a,
        "set_b": set_b,
        "set_c": set_c
    }

    with open("grammar.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4)
        
    log_audit("COMPLETE", f"🎉 Finished! Saved {len(set_a) + len(set_b) + len(set_c)} questions to grammar.json.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"🚨 **CRITICAL ERROR (Grammar Generator):**\nYour GitHub Action failed to generate today's grammar sets!\n\n`{e}`",
                "parse_mode": "Markdown"
            })
        print(f"Fatal pipeline error: {e}")
