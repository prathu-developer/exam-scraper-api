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

# --- TELEGRAM PREVIEW SENDER ---
def send_telegram_preview(final_json_string):
    """Sends a short confirmation DM to the Admin with a GitHub link."""
    BOT_TOKEN = "8730359477:AAFuFqqTUFMVPCfD-0raaZxrgUeIGGOBNFM"
    ADMIN_CHAT_ID = "716496729"
    
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
   # 1. Gather all 4 Editorials
    hindu_texts = get_hindu_editorials()
    ie_texts = get_indian_express_editorials()
    massive_context = "\n\n---\n\n".join(hindu_texts + ie_texts)
    
    # 💾 Create the Audit Log and save the raw editorials
    with open('vocab_audit_log.md', 'w', encoding='utf-8') as log_file:
        log_file.write("# 🧠 Vocab Generation Audit Log\n\n## 📰 PREP: Raw Editorials\n```text\n" + massive_context + "\n```\n\n")
        
    # Load your exact prompts (Paste your massive prompts here)
    PROMPT_1_EXTRACT = f"""[ROLE

                            You are a Senior Lexicographer specializing in vocabulary for SSC CGL, IBPS PO, SBI PO, RBI Grade B, UPSC, and other competitive examinations.
                            
                            OBJECTIVE
                            
                            Read the editorial carefully and extract ALL possible advanced lexical candidates.
                            
                            Do NOT rank them.
                            Do NOT filter them aggressively.
                            Do NOT limit yourself to 25 items.
                            
                            Your only goal is to collect every vocabulary item that could potentially deserve consideration later.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━
                            
                            INCLUDE
                            
                            Extract any item that satisfies ONE OR MORE of the following:
                            
                            • Advanced vocabulary (preferably C1/C2)
                            • Literary vocabulary
                            • Academic vocabulary
                            • Sophisticated editorial vocabulary
                            • Advanced phrasal verbs
                            • Advanced idioms
                            • High-quality collocations
                            • Editorial expressions commonly useful in competitive exams
                            
                            ━━━━━━━━━━━━━━━━━━━━━━
                            
                            EXCLUDE
                            
                            Do NOT extract:
                            
                            • Proper nouns
                            • Names of people
                            • Countries
                            • Cities
                            • Organizations
                            • Political parties
                            • Dates
                            • Numbers
                            • Acronyms
                            • Newspaper-specific references
                            • Citations
                            • URLs
                            • Footnotes
                            • Headlines
                            • Captions
                            
                            ━━━━━━━━━━━━━━━━━━━━━━
                            
                            NORMALIZATION RULES
                            
                            • Keep every item only once.
                            • Preserve original spelling.
                            • Preserve phrasal verbs exactly.
                            • Preserve idioms exactly.
                            • Do not stem or modify words.
                            • Ignore capitalization differences.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━
                            
                            IMPORTANT
                            
                            This is ONLY a candidate collection stage.
                            
                            Do NOT decide whether a word is too common.
                            Do NOT decide whether a word is too technical.
                            Do NOT decide whether it should finally appear in the quiz.
                            
                            When in doubt,
                            include it.
                            
                            It is better to collect too many candidates than to miss a valuable one.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━
                            
                            OUTPUT FORMAT
                            
                            Return ONLY a numbered list.
                            
                            Example
                            
                            1. delineate
                            2. fastidious
                            3. throw cold water on
                            4. burgeoning
                            5. at loggerheads
                            
                            Do not add explanations.
                            Do not add definitions.
                            Do not add CEFR levels.
                            Do not add any extra text.]\n\nEDITORIAL:\n{massive_context}"""
    
    print("🧠 Stage 1: Extracting Candidates...")
    candidates = call_gemini_with_rotation(PROMPT_1_EXTRACT)
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## 🎯 PROMPT 1: All Extracted Candidates\n```text\n" + candidates + "\n```\n\n")
        
    time.sleep(3) # Short breather for the API
    
    PROMPT_2_FILTER = f"""[ROLE

                            You are a Senior Lexicographer and Competitive Exam Vocabulary Specialist for SSC CGL, IBPS PO, SBI PO, RBI Grade B, UPSC, CAT, and other high-level competitive examinations.
                            
                            OBJECTIVE
                            
                            You are given a list of vocabulary candidates extracted from an editorial.
                            
                            Your task is to select the BEST 25 items that are genuinely valuable for competitive exam aspirants.
                            
                            This is a filtering and ranking task.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            PRIMARY SELECTION PRINCIPLE
                            
                            Prefer quality over rarity.
                            
                            Every selected item should satisfy as many of these conditions as possible:
                            
                            • Frequently appears in quality editorials.
                            • Useful for SSC and Banking vocabulary.
                            • Useful beyond a single article.
                            • Worth remembering permanently.
                            • High lexical value.
                            • Naturally usable in English.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            DIFFICULTY FILTER
                            
                            STRICTLY EXCLUDE
                            
                            • A1
                            • A2
                            • B1
                            • B2 vocabulary
                            
                            EXCLUDE COMMON C1/C2 WORDS
                            
                            Unless they are exceptionally important, remove common editorial words such as
                            
                            volatility
                            constraints
                            rollback
                            self-determination
                            consensus
                            trajectory
                            mitigate
                            resilience
                            scrutiny
                            precedent
                            
                            Apply the same principle to similar overused editorial vocabulary.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            PREFERENCE ORDER
                            
                            Highest Priority
                            
                            • Sophisticated editorial vocabulary
                            • Literary vocabulary
                            • Academic vocabulary
                            • Elegant verbs
                            • Elegant adjectives
                            • Powerful abstract nouns
                            
                            Medium Priority
                            
                            • Advanced collocations
                            • Advanced phrasal verbs
                            • Advanced idioms
                            
                            Lower Priority
                            
                            • Technical terminology
                            • Legal jargon
                            • Scientific jargon
                            • Financial jargon
                            
                            Keep technical terms only if they have broad editorial and competitive-exam relevance.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            REMOVE
                            
                            Remove
                            
                            • duplicates
                            • spelling variants
                            • near duplicates
                            • proper nouns
                            • newspaper-specific phrases
                            • one-time expressions
                            • context-dependent phrases
                            • obscure terminology
                            • words useful only inside this article
                            • legal or administrative terms that function as concepts rather than vocabulary
                            • multi-word expressions that cannot naturally be asked in a synonym or antonym question
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            BALANCE RULE
                            
                            Maintain a healthy mixture of
                            
                            verbs
                            
                            adjectives
                            
                            nouns
                            
                            idioms
                            
                            phrasal verbs
                            
                            Do not let one category dominate unless the article naturally demands it.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            EDITORIAL SENSE
                            
                            If a word has multiple meanings,
                            
                            select it only if its editorial meaning is useful for competitive examinations.
                            
                            Ignore highly technical or uncommon meanings.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            FINAL QUALITY TEST

                            Before finalizing each item, ask ALL of the following:
                            
                            1. Would this naturally appear as a standalone vocabulary question in SSC CGL, IBPS PO, SBI PO, RBI Grade B, UPSC, CAT or GRE?
                            
                            2. Is this useful outside the context of this particular editorial?
                            
                            3. Can this be tested directly through a synonym or antonym question?
                            
                            4. Is this a genuine vocabulary item rather than a legal, political or administrative concept?
                            
                            5. Would learning this item improve a student's long-term competitive exam vocabulary?
                            
                            If the answer to ANY of Questions 1, 3 or 4 is NO, deprioritize the item in favor of a stronger lexical alternative.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            OUTPUT
                            
                            Return ONLY the selected 25 items in the following format.
                            
                            Word: <word>
                            Part of Speech: <Noun | Verb | Adjective | Adverb | Phrasal Verb | Idiom | Collocation>
                            
                            Example
                            
                            Word: Delineate
                            Part of Speech: Verb
                            
                            Word: Fastidious
                            Part of Speech: Adjective
                            
                            Word: At loggerheads
                            Part of Speech: Idiom
                            
                            Word: Throw cold water on
                            Part of Speech: Phrasal Verb
                            
                            Repeat this format for all 25 selected items.
                            
                            Do not include definitions.
                            Do not include CEFR labels.
                            Do not include explanations.
                            Do not include numbering.
                            Do not include markdown.
                            
                            ━━━━━━━━━━━━━━━━━━━━━━━━━━
                            
                            INPUT]\n\nINPUT:\n{candidates}"""
    print("🧠 Stage 2: Filtering Top 25...")
    top_25 = call_gemini_with_rotation(PROMPT_2_FILTER)
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## 🏆 PROMPT 2: Filtered Top 25 Finalists\n```text\n" + top_25 + "\n```\n\n")
        
    time.sleep(3)
    
    PROMPT_3_GENERATE = f"""[ROLE

You are a Senior Competitive Exam Question Setter specializing in SSC CGL, IBPS PO, SBI PO, RBI Grade B and other government examinations.

Your responsibility is to create a high-quality vocabulary quiz from the supplied word list.

━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT

INPUT

You will receive exactly 25 vocabulary items.

Each item contains

• Word
• Part of Speech

Example

Word: Delineate
Part of Speech: Verb

Use the supplied Part of Speech while generating options.

Every option must belong to that same Part of Speech.

Do not infer or change the supplied Part of Speech.

━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION FORMAT

Generate exactly 25 questions.

Questions 1–15

What is the SIMILAR meaning of '[Word]'?

Questions 16–25

What is the OPPOSITE meaning of '[Word]'?

━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTION RULES

Each question must contain exactly four options.

Exactly ONE option must be correct.

The remaining three must be plausible distractors.

━━━━━━━━━━━━━━━━━━━━━━━━━━

DISTRACTOR DESIGN

Generate the correct answer FIRST.

Then generate exactly THREE incorrect options.

Do NOT generate all four options simultaneously.

Each incorrect option must be selected independently.

━━━━━━━━━━━━━━━━━━━━━━━━━━

DISTRACTOR SELECTION RULES

Each distractor MUST satisfy ALL of the following:

• Same part of speech.
• Similar CEFR difficulty.
• Belongs to the same semantic family.
• Could realistically confuse a well-prepared SSC CGL or IBPS PO aspirant.
• Grammatically interchangeable in many contexts.
• Accepted in standard English dictionaries.

━━━━━━━━━━━━━━━━━━━━━━━━━━

DO NOT use distractors that are selected only because they

• start with similar letters
• have similar spelling
• have similar pronunciation
• share prefixes or suffixes
• merely look visually similar

Similarity must be semantic, NOT orthographic.

━━━━━━━━━━━━━━━━━━━━━━━━━━

SELF-CHECK

Before finalizing the options, verify:

Would a student need to genuinely know the meaning of the target word to eliminate every incorrect option?

If NO,

replace the weak distractor.

Repeat until all four options are believable.
━━━━━━━━━━━━━━━━━━━━━━━━━━

CORRECT ANSWER

Use the meaning most commonly found in

• editorials

• SSC examinations

• Banking examinations

Do not use obscure dictionary meanings.

━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTION ORDER

Randomize the correct answer independently for every question.

Do NOT follow any visible pattern.

━━━━━━━━━━━━━━━━━━━━━━━━━━

EXPLANATION

Maximum 150 characters.

Explain

• meaning of the target word

• why the correct option is correct

Use simple English.

━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT FORMAT

Return ONLY a valid JSON array.

JSON Schema

[
{{
"question":"1. What is the SIMILAR meaning of 'Word'?",
"options":[
"Option A",
"Option B",
"Option C",
"Option D"
],
"correct_answer":"Exact option text",
"explanation":"Maximum 150 characters."
}}
]

━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT WORDS]\n\nINPUT WORDS:\n{top_25}"""
    print("🧠 Stage 3: Generating JSON Quiz...")
    raw_json = call_gemini_with_rotation(PROMPT_3_GENERATE)
    
    # Strip markdown code blocks if Gemini added them
    raw_json = raw_json.replace("```json", "").replace("```", "").strip()
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## ⚙️ PROMPT 3: Raw Unchecked JSON\n```json\n" + raw_json + "\n```\n\n")
        
    time.sleep(3)
    
    PROMPT_4_QA = f"""[ROLE

You are the Chief Quality Reviewer for SSC CGL, IBPS PO, SBI PO, RBI Grade B and other competitive examinations.

You are NOT generating a new quiz.

You are reviewing an already generated vocabulary quiz.

Your responsibility is to detect every possible flaw and automatically correct it.

━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT

You will receive a JSON vocabulary quiz.

Review every question independently.

━━━━━━━━━━━━━━━━━━━━━━━━━━

VALIDATION CHECKLIST

For every question verify ALL of the following.

1. Exactly ONE correct answer exists.

2. The correct answer is unquestionably correct in standard English.

3. The meaning used matches the editorial/common competitive exam sense.

4. Every option belongs to the SAME part of speech.

5. Every option is approximately the SAME CEFR difficulty.

6. Every distractor is plausible.

7. No distractor is accidentally another correct answer.

8. No distractor is an obvious opposite in synonym questions.

9. No distractor is an obvious synonym in antonym questions.

10. No distractor is completely unrelated.

11. No duplicate options exist.

12. No spelling mistakes exist.

13. No grammatical mistakes exist.

14. Explanation length does not exceed 150 characters.

15. Explanation correctly justifies the answer.

16. Randomization of answer positions does not show an obvious pattern.

17. Every question follows SSC CGL / Banking examination standards.

━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTO-CORRECTION RULE

Treat every question as if it is being reviewed by the Chief Examiner of SSC CGL and IBPS PO.

If a question does NOT meet competitive examination standards, you MUST improve it before returning the final JSON.

When reviewing each question, follow this priority order:

1. Verify that the correct answer is unquestionably correct.

2. Evaluate the QUALITY of the distractors.

Reject the distractors if ANY of the following is true:

• One or more options can be eliminated immediately.
• The incorrect options belong to unrelated semantic fields.
• The incorrect options are noticeably easier than the target word.
• The incorrect options are unrealistic or artificial.
• The question can be answered without knowing the vocabulary.

If any of these occur, REPLACE the distractors with stronger alternatives.

3. Preserve the original target word whenever possible.

4. Rewrite explanations only if they are incorrect or unclear.

5. Re-randomize option order whenever options are replaced.

The objective is NOT merely to produce a correct question.

The objective is to produce a question that could realistically appear in SSC CGL or IBPS PO.

━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAM STANDARD TEST

For every question ask yourself:

Would this question survive unchanged if reviewed by an experienced SSC CGL or IBPS PO paper setter?

If NO,

improve the question before returning it.

Do not accept merely correct questions.

Accept only examination-quality questions.
━━━━━━━━━━━━━━━━━━━━━━━━━━

DO NOT

Do NOT change question numbering.

Do NOT change JSON structure.

Do NOT add new questions.

Do NOT remove questions.

Do NOT change a correct question.

━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT

Return ONLY the corrected JSON array.

If no corrections are required,

return the original JSON unchanged.

Do not add any explanation.

Do not add any commentary.

Do not use Markdown.

━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT JSON]\n\nINPUT JSON:\n{raw_json}"""
    print("🧠 Stage 4: Quality Review & Auto-Correction...")
    final_json = call_gemini_with_rotation(PROMPT_4_QA)
    final_json = final_json.replace("```json", "").replace("```", "").strip()
    
    with open('vocab_audit_log.md', 'a', encoding='utf-8') as log_file:
        log_file.write("## ✅ PROMPT 4: Final Flawless JSON\n```json\n" + final_json + "\n```\n\n")
        
    # Save the flawless quiz
    with open('questions.json', 'w', encoding='utf-8') as f:
        f.write(final_json)
    print("✅ Successfully built and saved questions.json!")
    
    # Send the DM preview to Prathu!
    send_telegram_preview(final_json)

if __name__ == "__main__":
    run_vocab_pipeline()
