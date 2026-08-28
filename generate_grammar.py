import os
import json
import time
import requests
import random
from datetime import datetime
from google import genai
from google.genai import types # type: ignore

# --- 1. SETUP CREDENTIALS ---
KEYS = [
    os.environ.get("GEMINI_KEY_1"),
    os.environ.get("GEMINI_KEY_2"),
    os.environ.get("GEMINI_KEY_3")
]

# ✨ Model rotation fallback list
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
    with open("grammar_audit_log.txt", "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

grammar_topics = [
    "Subject Verb Agreement", "Tenses", "Articles", "Prepositions", "Pronouns", 
    "Determiners", "Conjunctions", "Parallelism", "Comparisons", "Infinitive vs Gerund", 
    "Participles", "Modifier Placement", "Relative Pronouns", "Relative Clauses", 
    "Conditionals", "Modals", "Sequence of Tenses", "Active and Passive Voice", 
    "Reported Speech", "Fixed Expressions"
]

# Paste the ENTIRE topic_subrules dictionary from the suggested file here. 
# (I am omitting the 180 rules here to keep this short, but paste the full topic_subrules { ... } block here)
topic_subrules = {

    # --------------------------------------------------------
    # 1. SUBJECT-VERB AGREEMENT
    # --------------------------------------------------------
    "Subject Verb Agreement": [
        "Each / every + singular noun + singular verb",
        "Each of + plural noun + singular verb",
        "Every one of + plural noun + singular verb",
        "Everyone / everybody + singular verb",
        "Someone / somebody + singular verb",
        "Anyone / anybody + singular verb",
        "No one / nobody + singular verb",
        "Either / neither as singular subject",
        "Either of + plural noun + singular verb",
        "Neither of + plural noun + singular verb",
        "One of + plural noun + singular verb",
        "A number of + plural noun + plural verb",
        "The number of + plural noun + singular verb",
        "More than one + singular noun + singular verb",
        "Many a + singular noun + singular verb",
        "Either...or / neither...nor agreement",
        "Not only...but also agreement",
        "Agreement with nearest subject",
        "Along with / as well as does not change subject",
        "Together with does not change subject",
        "Subject separated from verb by prepositional phrase",
        "Subject separated from verb by relative clause",
        "Collective noun as a single unit",
        "Collective noun referring to individuals",
        "News / mathematics / politics as singular",
        "Police / cattle / people as plural",
        "Scissors / trousers / spectacles as plural",
        "A pair of + plural noun + singular verb",
        "Compound subject joined by and",
        "Compound subject expressing one idea",
        "There is / there are agreement",
        "Gerund phrase as singular subject",
        "Infinitive phrase as singular subject",
        "What-clause as singular subject"
    ],


    # --------------------------------------------------------
    # 2. TENSES
    # --------------------------------------------------------
    "Tenses": [
        "Simple present for habitual action",
        "Simple present for general truth",
        "Simple present for scheduled future",
        "Present continuous for action happening now",
        "Present continuous for planned future",
        "Stative verbs and continuous forms",
        "Present perfect with since",
        "Present perfect with for",
        "Present perfect with already / yet",
        "Present perfect with just",
        "Present perfect with ever / never",
        "Present perfect vs simple past",
        "Present perfect continuous for duration",
        "Simple past for completed past action",
        "Past continuous for interrupted action",
        "Past perfect for earlier past action",
        "Past perfect with before / after",
        "Past perfect with by the time",
        "Past perfect continuous",
        "Used to for past habit",
        "Would for repeated past action",
        "Future continuous",
        "Future perfect",
        "Future perfect continuous",
        "No future tense after when / if",
        "No future tense after until / before / after",
        "It is time + past tense",
        "It is high time + past tense",
        "Wish + past",
        "Wish + past perfect",
        "As if / as though + appropriate tense",
        "No sooner...than",
        "Hardly...when",
        "Scarcely...when"
    ],


    # --------------------------------------------------------
    # 3. ARTICLES
    # --------------------------------------------------------
    "Articles": [
        "A before consonant sound",
        "An before vowel sound",
        "A / an with singular countable noun",
        "A / an with professions",
        "A / an meaning one",
        "The for specific reference",
        "The for previously mentioned noun",
        "The for unique objects",
        "The with superlatives",
        "The with ordinals",
        "The with same / only",
        "The with rivers / seas / oceans",
        "The with mountain ranges",
        "The with island groups",
        "The with deserts",
        "The with newspapers",
        "The with plural geographical names",
        "Zero article with proper names",
        "Zero article with languages / subjects",
        "Zero article with sports",
        "Zero article with meals",
        "Zero article with abstract nouns in general sense",
        "Institutional use of school / hospital / prison / church",
        "Building use vs institutional use",
        "Article with bed / home / work",
        "A few vs few",
        "A little vs little"
    ],


    # --------------------------------------------------------
    # 4. PREPOSITIONS
    # --------------------------------------------------------
    "Prepositions": [
        "At / on / in for time",
        "At / on / in for place",
        "Since vs for",
        "By vs until",
        "Between vs among",
        "Beside vs besides",
        "Into vs in",
        "Onto vs on",
        "By vs with",
        "In vs by transport",
        "During vs for",
        "Within vs in",
        "Through vs throughout",
        "Across vs along",
        "Over vs above",
        "Under vs below",
        "To vs for",
        "Despite vs in spite of",
        "Because vs because of",
        "Due to vs owing to",
        "Different from",
        "Similar to",
        "Prefer to",
        "Senior to",
        "Junior to",
        "Superior to",
        "Inferior to",
        "Responsible for",
        "Interested in",
        "Capable of",
        "Accused of",
        "Aware of",
        "Prevent from",
        "Insist on",
        "Object to",
        "Succeed in",
        "Persist in",
        "Participate in",
        "Refer to",
        "Result in vs result from",
        "Apply to vs apply for",
        "Comply with",
        "Conform to"
    ],


    # --------------------------------------------------------
    # 5. PRONOUNS
    # --------------------------------------------------------
    "Pronouns": [
        "Subject pronoun vs object pronoun",
        "I vs me",
        "He / him and she / her",
        "We / us and they / them",
        "Who vs whom",
        "Who as subject",
        "Whom as object",
        "Reflexive pronoun with same subject",
        "Personal pronoun vs reflexive pronoun",
        "Possessive adjective vs possessive pronoun",
        "My vs mine",
        "Your vs yours",
        "Their vs theirs",
        "Its vs it's",
        "Each other vs one another",
        "One / ones substitution",
        "This / that reference",
        "These / those reference",
        "Either / neither as pronouns",
        "None / both / all as pronouns",
        "Pronoun agreement with indefinite pronouns",
        "Pronoun with compound antecedent",
        "Ambiguous pronoun reference"
    ],


    # --------------------------------------------------------
    # 6. DETERMINERS
    # --------------------------------------------------------
    "Determiners": [
        "Much vs many",
        "Few vs a few",
        "Little vs a little",
        "Fewer vs less",
        "Number vs amount",
        "Each vs every",
        "Either vs neither",
        "Both vs all",
        "Some vs any",
        "No vs not any",
        "Another vs other",
        "Other vs others",
        "The other vs another",
        "Others vs the others",
        "Enough + noun",
        "Enough after adjective / adverb",
        "Too much vs too many",
        "So much vs so many",
        "Such vs such a / an",
        "What vs what a / an",
        "A number of vs the number of"
    ],


    # --------------------------------------------------------
    # 7. CONJUNCTIONS
    # --------------------------------------------------------
    "Conjunctions": [
        "Either...or",
        "Neither...nor",
        "Both...and",
        "Not only...but also",
        "Whether...or",
        "As well as",
        "Rather than",
        "Although vs though",
        "Although...but error",
        "Because...therefore error",
        "Despite / in spite of",
        "Because vs because of",
        "While for contrast",
        "Whereas",
        "Unless",
        "Until",
        "Provided / providing that",
        "As long as",
        "Lest",
        "So...that",
        "Such...that",
        "Too...to"
    ],


    # --------------------------------------------------------
    # 8. PARALLELISM
    # --------------------------------------------------------
    "Parallelism": [
        "Parallel nouns",
        "Parallel adjectives",
        "Parallel adverbs",
        "Parallel verbs",
        "Parallel infinitives",
        "Parallel gerunds",
        "Parallel participles",
        "Parallel phrases after and / or",
        "Either...or parallelism",
        "Neither...nor parallelism",
        "Both...and parallelism",
        "Not only...but also parallelism",
        "Prefer X to Y parallelism",
        "Faulty list construction"
    ],


    # --------------------------------------------------------
    # 9. COMPARISONS
    # --------------------------------------------------------
    "Comparisons": [
        "Comparative + than",
        "Superlative + the",
        "Comparative for two",
        "Superlative for more than two",
        "As...as",
        "Not as...as",
        "Less...than",
        "Fewer...than",
        "Much / far + comparative",
        "By far + superlative",
        "One of the + superlative + plural noun",
        "The more...the more",
        "The less...the less",
        "Double comparative",
        "Double superlative",
        "More better type error",
        "Senior / junior + to",
        "Superior / inferior + to",
        "Prefer + to",
        "Different from",
        "Elder vs older",
        "Farther vs further"
    ],


    # --------------------------------------------------------
    # 10. INFINITIVE VS GERUND
    # --------------------------------------------------------
    "Infinitive vs Gerund": [
        "Gerund after preposition",
        "Gerund after enjoy",
        "Gerund after avoid",
        "Gerund after admit",
        "Gerund after deny",
        "Gerund after suggest",
        "Gerund after consider",
        "Gerund after mind",
        "Gerund after finish",
        "Gerund after postpone",
        "Infinitive after want",
        "Infinitive after decide",
        "Infinitive after hope",
        "Infinitive after plan",
        "Infinitive after agree",
        "Infinitive after refuse",
        "Infinitive after promise",
        "Infinitive after expect",
        "Infinitive after manage",
        "Infinitive after fail",
        "Make + object + base verb",
        "Let + object + base verb",
        "Help + object + infinitive / base verb",
        "Stop doing vs stop to do",
        "Remember doing vs remember to do",
        "Forget doing vs forget to do",
        "Try doing vs try to do",
        "Look forward to + gerund",
        "Be used to + gerund",
        "Used to + base verb"
    ],


    # --------------------------------------------------------
    # 11. PARTICIPLES
    # --------------------------------------------------------
    "Participles": [
        "Present participle as adjective",
        "Past participle as adjective",
        "Having + V3",
        "Having been + V3",
        "Present participle for simultaneous action",
        "Past participle for passive meaning",
        "Correct participial phrase subject",
        "Dangling participle",
        "Misplaced participial phrase",
        "Reduced active relative clause",
        "Reduced passive relative clause",
        "Being + V3",
        "Participle vs gerund",
        "Bored vs boring",
        "Interested vs interesting",
        "Confused vs confusing"
    ],


    # --------------------------------------------------------
    # 12. MODIFIER PLACEMENT
    # --------------------------------------------------------
    "Modifier Placement": [
        "Dangling modifier",
        "Misplaced modifier",
        "Squinting modifier",
        "Only placement",
        "Almost / nearly placement",
        "Enough placement",
        "Too placement",
        "Introductory modifier with correct subject",
        "Participial phrase attachment",
        "Infinitive phrase modifier",
        "Prepositional phrase modifier",
        "Adverb modifying intended word"
    ],


    # --------------------------------------------------------
    # 13. RELATIVE PRONOUNS
    # --------------------------------------------------------
    "Relative Pronouns": [
        "Who for persons",
        "Whom for object",
        "Whose for possession",
        "Which for things",
        "That in restrictive clauses",
        "That after superlative",
        "That after all / everything / nothing",
        "That after the only",
        "Which after comma",
        "Who vs whom",
        "Whose referring to things",
        "Where for place",
        "When for time",
        "Why for reason",
        "Omission of object relative pronoun",
        "Subject relative pronoun cannot be omitted",
        "Preposition + whom",
        "Preposition + which",
        "What vs that"
    ],


    # --------------------------------------------------------
    # 14. RELATIVE CLAUSES
    # --------------------------------------------------------
    "Relative Clauses": [
        "Defining relative clause",
        "Non-defining relative clause",
        "Comma in non-defining clause",
        "That in non-defining clause",
        "Relative pronoun omission",
        "Reduced relative clause",
        "Active reduced relative clause",
        "Passive reduced relative clause",
        "Correct antecedent",
        "Ambiguous antecedent",
        "Agreement inside relative clause",
        "Tense inside relative clause"
    ],


    # --------------------------------------------------------
    # 15. CONDITIONALS
    # --------------------------------------------------------
    "Conditionals": [
        "Zero conditional",
        "First conditional",
        "Second conditional",
        "Third conditional",
        "Mixed conditional",
        "If + present + present",
        "If + present + will",
        "If + past + would",
        "If + past perfect + would have",
        "If I were",
        "Unless",
        "Provided that",
        "As long as",
        "Had I known",
        "Were I to",
        "Should you"
    ],


    # --------------------------------------------------------
    # 16. MODALS
    # --------------------------------------------------------
    "Modals": [
        "Can for ability",
        "Could for past ability",
        "Can / could for possibility",
        "May for permission",
        "May vs might",
        "Must for obligation",
        "Must for strong inference",
        "Have to vs must",
        "Need to",
        "Needn't",
        "Should for advice",
        "Should for expectation",
        "Ought to",
        "Would for polite request",
        "Would for past habit",
        "Would rather",
        "Modal + base verb",
        "Should / could / would / might have + V3"
    ],


    # --------------------------------------------------------
    # 17. SEQUENCE OF TENSES
    # --------------------------------------------------------
    "Sequence of Tenses": [
        "Past reporting verb + past tense",
        "Past reporting verb + past perfect",
        "Universal truth remains present",
        "Scientific fact remains present",
        "Since clause sequence",
        "Before / after sequence",
        "By the time sequence",
        "When clause sequence",
        "Until clause sequence",
        "As soon as sequence",
        "No future after time conjunction",
        "Unnecessary tense shift"
    ],


    # --------------------------------------------------------
    # 18. ACTIVE AND PASSIVE VOICE
    # --------------------------------------------------------
    "Active and Passive Voice": [
        "Simple present passive",
        "Simple past passive",
        "Simple future passive",
        "Present continuous passive",
        "Past continuous passive",
        "Present perfect passive",
        "Past perfect passive",
        "Modal passive",
        "Modal perfect passive",
        "Correct auxiliary in passive",
        "Correct past participle in passive",
        "Passive with two objects",
        "Passive with reporting verbs",
        "Intransitive verb cannot form ordinary passive"
    ],


    # --------------------------------------------------------
    # 19. REPORTED SPEECH
    # --------------------------------------------------------
    "Reported Speech": [
        "Statement reporting",
        "Yes / no question reporting",
        "Wh-question reporting",
        "Command reporting",
        "Request reporting",
        "Advice reporting",
        "Say vs tell",
        "Tell + object",
        "Backshift of present",
        "Backshift of present perfect",
        "Backshift of past",
        "Will to would",
        "Can to could",
        "May to might",
        "Pronoun change",
        "Time expression change",
        "Reported question word order",
        "No inversion in reported question",
        "Universal truth exception"
    ],


    # --------------------------------------------------------
    # 20. FIXED EXPRESSIONS
    # --------------------------------------------------------
    "Fixed Expressions": [
        "Accused of",
        "Acquainted with",
        "Addicted to",
        "Agree with a person",
        "Agree to a proposal",
        "Agree on a matter",
        "Apologise to someone for something",
        "Approve of",
        "Ashamed of",
        "Aware of",
        "Capable of",
        "Comply with",
        "Concentrate on",
        "Congratulate on",
        "Consist of",
        "Consistent with",
        "Contribute to",
        "Dependent on",
        "Eligible for",
        "Equivalent to",
        "Familiar with",
        "Famous for",
        "Fond of",
        "Guilty of",
        "Interested in",
        "Object to",
        "Opposed to",
        "Participate in",
        "Persist in",
        "Prevent from",
        "Proud of",
        "Qualified for",
        "Refer to",
        "Relevant to",
        "Responsible for",
        "Satisfied with",
        "Senior to",
        "Similar to",
        "Succeed in",
        "Superior to",
        "Tired of"
    ]
}

topic_weights = {
    "Subject Verb Agreement": 12, "Tenses": 11, "Prepositions": 11, "Articles": 8,
    "Pronouns": 8, "Determiners": 7, "Conjunctions": 7, "Parallelism": 5,
    "Comparisons": 5, "Infinitive vs Gerund": 8, "Participles": 4,
    "Modifier Placement": 4, "Relative Pronouns": 5, "Relative Clauses": 4,
    "Conditionals": 4, "Modals": 5, "Sequence of Tenses": 4,
    "Active and Passive Voice": 5, "Reported Speech": 5, "Fixed Expressions": 7
}

weighted_topics = []
for _topic, _weight in topic_weights.items():
    weighted_topics.extend([_topic] * _weight)

recent_grammar_rules = []
RECENT_RULE_MEMORY = 30

def remember_grammar_rule(topic, rule):
    key = (topic, rule)
    recent_grammar_rules.append(key)
    if len(recent_grammar_rules) > RECENT_RULE_MEMORY:
        del recent_grammar_rules[0]

def was_recently_used(topic, rule):
    return (topic, rule) in recent_grammar_rules

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
            day_offset = datetime.now().timetuple().tm_yday

            # SELECT TOPIC
            topic_seed = (day_offset * 1009 + master_chunk_idx * 37 + topic_offset * 101)
            topic_rng = random.Random(topic_seed)
            topic = topic_rng.choice(weighted_topics)

            # SELECT SPECIFIC RULE
            available_rules = [
                rule for rule in topic_subrules[topic]
                if not was_recently_used(topic, rule)
            ]

            if not available_rules:
                available_rules = topic_subrules[topic]

            rule_seed = (day_offset * 2027 + master_chunk_idx * 73 + topic_offset * 149)
            rule_rng = random.Random(rule_seed)
            specific_rule = rule_rng.choice(available_rules)

            remember_grammar_rule(topic, specific_rule)

            # ERROR LOCATION (Updated to descriptive parts instead of A/B/C/D)
            error_parts = [
                "the third part", "the first part", "the fourth part", "the second part",
                "the first part", "the fourth part", "the second part", "the third part",
                "the second part", "the third part", "the first part", "the fourth part",
                "the fourth part", "the second part", "the third part", "the first part"
            ]
            error_part = error_parts[master_chunk_idx % len(error_parts)]
            
            log_audit(
                "PROMPT",
                f"[{set_name}] Attempting Q{len(successful_mcqs)+1}/{target_count} | "
                f"Chunk: {master_chunk_idx+1}/15 | Topic: {topic} | Rule: {specific_rule} | Error Part: {error_part}"
            )
            
            current_prompt = (
                prompt
                .replace("{CHUNK_TEXT}", chunks[master_chunk_idx])
                .replace("{GRAMMAR_TOPIC}", topic)
                .replace("{SPECIFIC_RULE}", specific_rule)
                .replace("{ERROR_PART}", error_part)
            )
            
            mcq = None
            max_chunk_retries = 3
            
            for retry_attempt in range(max_chunk_retries):
                if mcq: 
                    break # Break out if we successfully got a question!
                
                # Iterate across all Keys and rotate across Models
                for attempt in range(len(KEYS)):
                    if not KEYS[attempt]: continue
                    temp_client = genai.Client(api_key=KEYS[attempt])
                    
                    key_success = False
                    for model_name in MODELS:
                        try:
                            log_audit("API_CALL", f"[{set_name}] Attempting Key {attempt+1} with {model_name}...")
                            
                            response = temp_client.models.generate_content(
                                model=model_name, 
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
                            key_success = True
                            break # Success! Break model loop
                            
                        except Exception as e:
                            error_msg = str(e).lower()
                            
                            if "429" in error_msg or "quota" in error_msg:
                                log_audit("API_WARN", f"[{set_name}] Key {attempt+1} ({model_name}) quota exhausted. Falling back...")
                                continue # Try next model on this key or next key
                                
                            elif "503" in error_msg or "unavailable" in error_msg:
                                log_audit("API_WARN", f"[{set_name}] 503 Overload on Key {attempt+1} ({model_name}). Waiting 30s...")
                                time.sleep(30)
                                continue
                                
                            else:
                                log_audit("API_WARN", f"[{set_name}] Error on Key {attempt+1} ({model_name}): {error_msg[:40]}...")
                                time.sleep(5)

                    if key_success:
                        break # Break out of key-rotation loop on success

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
        Target Grammar Topic: {GRAMMAR_TOPIC}
        Specific Sub-Rule to Test: {SPECIFIC_RULE}
        
        Generate the question strictly focusing on the specific sub-rule mentioned above. 
        The primary grammatical error MUST primarily test this exact sub-rule, not just the general topic.

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
        5. Divide the sentence into EXACTLY four parts separated by slashes (/). Do NOT label them with (A), (B), (C), or (D).
        6. The fifth option MUST be "No error".
        7. The incorrect portion must appear ONLY in {ERROR_PART}.
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
        10. Avoid extremely rare grammar rules.
        11. The error MUST belong to a standard competitive exam grammar topic.
        12. Explanation must be detailed and clear, stating:
        - what is wrong
        - why it is wrong
        - the correct form and the underlying grammar rule in detail
        13. Do NOT mention option numbers or alphabets (A, B, C, D) in the options array or the explanation. The options must just be the raw text.
        14. Before returning, verify:
        • Exactly one answer is correct.
        • The assigned grammar topic is actually being tested.
        • The error appears only in {ERROR_PART}.
        • The error is not visually obvious.
        • The question resembles an actual SSC/IBPS previous-year paper.

        Return EXACTLY this JSON structure:
        {
            "instruction": "Directions: In the following sentence, one part may contain an error. Identify that part. If there is no error, choose No error.",
            "sentence": "Neither of the two proposals / were considered suitable / for immediate implementation / by the planning committee.",
            "options":[
                "Neither of the two proposals",
                "were considered suitable",
                "for immediate implementation",
                "by the planning committee.",
                "No error"
            ],
            "correct_answer":"were considered suitable",
            "explanation":"Use 'was' instead of 'were'. 'Neither of' is followed by a plural noun but takes a singular verb."
        }
        """

    prompt_B = """
        You are India's best English question setter for SSC CGL Tier-II, SSC CHSL, SSC CPO, IBPS PO, SBI PO, SBI Clerk, RBI Assistant and other competitive exams.
        Editorial Context:
        "{CHUNK_TEXT}"

        Create EXACTLY ONE Sentence Improvement question.

        Target Grammar Topic: {GRAMMAR_TOPIC}
        Specific Sub-Rule to Test: {SPECIFIC_RULE}
        
        Generate the question strictly focusing on the specific sub-rule mentioned above. 
        The primary grammatical error MUST primarily test this exact sub-rule, not just the general topic.
        Supporting grammar may appear naturally, but the corrected phrase should mainly assess this topic.

        STRICT RULES
        1. Difficulty must match recent SSC CGL Tier-II and Banking PO exams.
        2. Use natural newspaper-quality English inspired by the editorial context. 
        The sentence should resemble recent SSC CGL Tier-II and Banking PO questions by naturally incorporating subordinate clauses, relative clauses, participial phrases or modifiers where appropriate. Do not increase length unnecessarily.
        Do NOT create artificial or textbook sentences.
        Prefer realistic editorial sentence structures by naturally using subordinate clauses, relative clauses, participial phrases, appositives or modifiers where appropriate. Avoid unnecessarily simple sentence constructions.
        3. The complete sentence must be meaningful and grammatically correct AFTER applying the correct answer.
        4. Identify EXACTLY ONE continuous phrase (2-7 words) that needs improvement. Output this exact phrase in the "target_phrase" JSON field. Do NOT use HTML or underlines in the sentence itself.
        5. If the original phrase is incorrect:
           - Exactly ONE replacement option must be correct.
           - "No improvement" must be incorrect.
        6. If the original phrase is already correct:
           - The correct answer MUST be "No improvement".
           - Every replacement option must introduce a grammatical error.
        7. Provide EXACTLY four options. Do NOT use option letters (A, B, C, D) in the options array or the explanation.
        8. The fourth option MUST always be: "No improvement"
        9. Only ONE option can be correct.
        10. Focus ONLY on standard competitive exam grammar rules.
        11. Prefer grammar topics commonly tested in SSC and Banking:
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

        12. Do NOT test:
        - spelling
        - punctuation
        - capitalization
        - vocabulary meaning
        - style preferences

        13. Distractors must be realistic and resemble actual SSC/Banking options.
        14. Never allow more than one grammatically acceptable answer.
        15. Explanation must clearly and thoroughly state:
        - why the correct option is right without referring to an option letter
        - why the original or remaining options are grammatically incorrect

        16. Return ONLY valid JSON.

        Return EXACTLY this JSON:
        {
            "instruction": "Directions: In the following question, a part of the sentence is underlined. Below are given alternatives to the underlined part. Choose the option that best improves the sentence. If no improvement is needed, choose No improvement.",
            "target_phrase": "capable to handle",
            "sentence": "The manager is capable to handle difficult situations.",
            "options": [
                "capable of handling",
                "capable for handling",
                "capable in handling",
                "No improvement"
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
        3. Leave exactly one blank represented by "______".
        4. Provide EXACTLY 4 options. Do NOT use option letters (A, B, C, D) in the options array or the explanation.
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

        10. Never allow two options that can both fit.

        11. Explanation should thoroughly include:
        - contextual meaning of the correct word(s)
        - why they fit the overall editorial sentence
        - why each distractor fails grammatically or contextually

        12. Return ONLY valid JSON.

        Return EXACTLY this JSON structure:
        {
            "instruction": "Directions: In the following sentence, a word has been omitted. Choose the most appropriate word to fill in the blank.",
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
        4. Provide EXACTLY 4 options. Do NOT use option letters (A, B, C, D) in the options array or the explanation.
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

        12. Explanation should thoroughly include:
        - contextual meaning of the correct word(s)
        - why they fit the overall editorial sentence
        - why each distractor fails grammatically or contextually

        13. Return ONLY valid JSON.


        Return EXACTLY this JSON structure:
        {
            "instruction": "Directions: In the following sentence, two words have been omitted. Choose the most appropriate pair of words to fill in the blanks.",
            "sentence": "The company remained ______ despite the ______ market conditions.",
            "options": ["resilient, adverse", "fragile, favourable", "hesitant, optimistic", "rigid, stable"],
            "correct_answer": "resilient, adverse",
            "explanation": "Resilient means able to withstand shock, and adverse means unfavorable. This pair perfectly contrasts the company's strength against poor conditions."
        }
        """

    # --- 5. GENERATE & SAVE ---
    # Get current day of the week (0 = Monday, 1 = Tuesday, ..., 6 = Sunday)
    current_day = datetime.now().weekday()
    
    set_a = []
    # Set A: Mon (0), Tue (1), Thu (3), Sat (5)
    if current_day in [0, 1, 3, 5]:
        set_a = generate_with_bulldozer(
            prompt_A,
            5,
            "Set A (Error Detection)",
            topic_offset=0
        )
    
    set_b = []
    # Set B: Wed (2), Fri (4)
    if current_day in [2, 4]:
        set_b = generate_with_bulldozer(
            prompt_B,
            5,
            "Set B (Sentence Improvement)",
            topic_offset=9
        )
    
    set_c = []
    # Set C: Mon (0), Tue (1), Wed (2), Thu (3), Sat (5)
    if current_day in [0, 1, 2, 3, 5]:
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
