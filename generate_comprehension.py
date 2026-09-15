import os
import sys
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

# =====================================================================
# 1. SETUP CREDENTIALS & AUDIT LOGGING
# =====================================================================
API_KEYS = [
    os.environ.get("GEMINI_KEY_4"),
    os.environ.get("GEMINI_KEY_5"),
    os.environ.get("GEMINI_KEY_6")
]

MODELS = [
    'gemini-3.8-flash',
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash'
]

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MEMORY_FILE = "comprehension_memory.json"

def log_audit(step: str, details: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{step}] {details}\n"
    with open("comprehension_audit_log.txt", "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

# =====================================================================
# 2. RC ARCHETYPE BANK (84 EXAM STRUCTURES ACROSS 6 FAMILIES)
# =====================================================================
RC_STRUCTURE_BANK = {
    # Direct / Factual
    "RC_FACT_TRUE": {"family": "Fact", "templates": ["According to the passage, which statement is true?", "Which of the following statements is confirmed by the text?", "Based on the passage, which assertion is correct?"]},
    "RC_FACT_NOT_TRUE": {"family": "Fact", "templates": ["Which statement is NOT true according to the passage?", "Which of the following is incorrect based on the text?", "All of the following are supported EXCEPT:"]},
    "RC_FACT_DIRECT_SUPPORT": {"family": "Fact", "templates": ["Which statement is directly supported by the passage?", "Which claim is explicitly corroborated by the author?"]},
    "RC_FACT_CONTRADICTED": {"family": "Fact", "templates": ["Which of the following is contradicted by the passage?", "Which statement directly opposes the facts presented?"]},
    "RC_FACT_REASON": {"family": "Fact", "templates": ["What reason does the author give for the stated issue?", "Why does this development occur according to the text?"]},
    "RC_FACT_EFFECT": {"family": "Fact", "templates": ["What effect of the primary issue is mentioned in the passage?", "Which consequence is explicitly stated in the text?"]},
    "RC_FACT_DETAIL": {"family": "Fact", "templates": ["Which specific detail is explicitly stated regarding the subject?", "What detail does the passage provide about this situation?"]},
    "RC_FACT_EXAMPLE": {"family": "Fact", "templates": ["Which example is mentioned by the author to support the observation?", "What example is cited in the passage?"]},
    "RC_FACT_COMPARISON": {"family": "Fact", "templates": ["What comparison is made between the elements mentioned in the passage?", "How does the author compare the discussed viewpoints?"]},
    "RC_FACT_CHRONOLOGY": {"family": "Fact", "templates": ["What event occurred immediately according to the timeline in the passage?", "According to the passage, what followed the primary event?"]},
    "RC_FACT_AUTHOR_STATEMENT": {"family": "Fact", "templates": ["What does the author state regarding the subject?", "What observation does the author explicitly make?"]},
    "RC_FACT_MENTIONED": {"family": "Fact", "templates": ["Which of the following is mentioned in the passage?", "Which point is explicitly highlighted in the text?"]},
    "RC_FACT_NOT_MENTIONED": {"family": "Fact", "templates": ["Which of the following is NOT mentioned in the passage?", "Which element is omitted from the passage discussion?"]},
    "RC_FACT_COMBINATION": {"family": "Fact", "templates": ["Select the correct combination of statements:", "Which combination of the statements is accurate according to the passage?"]},
    "RC_FACT_STATEMENTS_I_II_III": {"family": "Fact", "templates": ["Consider statements (I), (II), and (III). Which are correct according to the passage?", "With reference to the passage, which of (I), (II), and (III) is/are true?"]},

    # Main Idea / Central Understanding
    "RC_MAIN_IDEA": {"family": "MainIdea", "templates": ["What is the central idea of the passage?", "The central theme of the passage revolves around:"]},
    "RC_MAIN_THEME": {"family": "MainIdea", "templates": ["What is the primary theme explored in the text?", "The passage primarily concerns:"]},
    "RC_MAIN_ARGUMENT": {"family": "MainIdea", "templates": ["What is the author's central argument?", "The primary contention made by the author is:"]},
    "RC_BEST_SUMMARY": {"family": "MainIdea", "templates": ["Which of the following best summarizes the passage?", "What is the most concise and accurate summary of the text?"]},
    "RC_APPROPRIATE_TITLE": {"family": "MainIdea", "templates": ["What is the most appropriate title for the passage?", "Which of the following serves as the best headline for the text?"]},
    "RC_PRIMARY_PURPOSE": {"family": "MainIdea", "templates": ["What is the primary purpose of the passage?", "The author's chief objective in writing this passage is to:"]},
    "RC_OVERALL_MESSAGE": {"family": "MainIdea", "templates": ["What is the overall message conveyed by the author?", "The key takeaway from the passage is that:"]},
    "RC_CENTRAL_THESIS": {"family": "MainIdea", "templates": ["What is the central thesis advanced in the passage?", "Which statement best captures the core thesis?"]},
    "RC_BEST_DESCRIPTION": {"family": "MainIdea", "templates": ["Which of the following best describes the passage as a whole?", "The passage can be most accurately described as:"]},

    # Inference / Implication
    "RC_INF_CAN": {"family": "Inference", "templates": ["What can be reasonably inferred from the passage?", "Which conclusion is best supported by the passage?"]},
    "RC_INF_CANNOT": {"family": "Inference", "templates": ["What CANNOT be inferred from the passage?", "Which conclusion does NOT follow logically from the text?"]},
    "RC_INF_CONCLUSION_FOLLOWS": {"family": "Inference", "templates": ["Which conclusion logically follows from the author's statements?", "What can be deduced from the passage?"]},
    "RC_INF_CONCLUSION_NOT_FOLLOWS": {"family": "Inference", "templates": ["Which of the following conclusions does NOT follow from the text?", "Which inference is invalid based on the passage?"]},
    "RC_INF_IMPLICATION": {"family": "Inference", "templates": ["What does the passage imply regarding the situation?", "The passage suggests which of the following?"]},
    "RC_INF_STRONGLY_SUPPORTED": {"family": "Inference", "templates": ["Which statement is most strongly supported by the passage?", "The evidence in the passage lends the greatest support to:"]},
    "RC_INF_LIKELY_CONSEQUENCE": {"family": "Inference", "templates": ["What is the likely consequence based on the passage?", "The passage implies that the current trend will lead to:"]},
    "RC_INF_REASONABLE_ASSUMPTION": {"family": "Inference", "templates": ["What can reasonably be assumed from the passage?", "The author's argument rests on which plausible assumption?"]},
    "RC_INF_UNDERLYING_ASSUMPTION": {"family": "Inference", "templates": ["What is the underlying assumption behind the argument?", "Which unstated premise supports the author's claim?"]},
    "RC_INF_COMBINED_FACTS": {"family": "Inference", "templates": ["Combining the facts presented, what can be deduced?", "What deduction emerges from synthesizing the passage evidence?"]},
    "RC_INF_SITUATION_CONSISTENT": {"family": "Inference", "templates": ["Which situation is most consistent with the passage?", "Which hypothetical scenario aligns with the author's viewpoint?"]},
    "RC_INF_SITUATION_INCONSISTENT": {"family": "Inference", "templates": ["Which situation is inconsistent with the passage?", "Which scenario directly contradicts the author's logic?"]},
    "RC_INF_CONDITION_CHANGE": {"family": "Inference", "templates": ["What would most likely happen if the primary condition changed?", "If the stated circumstances were altered, what outcome would logically follow?"]},
    "RC_INF_BEST_SUPPORTED": {"family": "Inference", "templates": ["Which inference is best supported by the passage?", "Which implicit point is most defensible based on the text?"]},

    # Author / Tone / Purpose
    "RC_TONE_PURPOSE": {"family": "AuthorTone", "templates": ["What is the author's primary purpose in discussing this issue?", "Why does the author address this topic?"]},
    "RC_TONE_INTENTION": {"family": "AuthorTone", "templates": ["What is the author's intention behind the main statement?", "The author intends to demonstrate that:"]},
    "RC_TONE_ATTITUDE": {"family": "AuthorTone", "templates": ["What is the author's attitude toward the subject matter?", "How does the author view the situation discussed?"]},
    "RC_TONE_OVERALL": {"family": "AuthorTone", "templates": ["What is the overall tone of the passage?", "The tone of the passage can best be described as:"]},
    "RC_TONE_STANCE": {"family": "AuthorTone", "templates": ["What is the author's overall stance on the issue?", "Which word best characterizes the author's stance?"]},
    "RC_TONE_POLARITY": {"family": "AuthorTone", "templates": ["Is the author's attitude toward the topic positive, negative, or neutral?", "The author evaluates the development with a tone that is:"]},
    "RC_TONE_CRITICAL": {"family": "AuthorTone", "templates": ["Why is the author critical of the observed trend?", "What aspect of the development does the author criticize?"]},
    "RC_TONE_ANALYTICAL": {"family": "AuthorTone", "templates": ["How does the author's analytical approach manifest in the discussion?", "The analytical focus of the author is aimed at:"]},
    "RC_TONE_CAUTIOUS": {"family": "AuthorTone", "templates": ["Why does the author adopt a cautious tone regarding the outcome?", "Where does the author express caution in the passage?"]},
    "RC_TONE_SCEPTICAL": {"family": "AuthorTone", "templates": ["What makes the author sceptical about the claims made?", "The author displays scepticism towards:"]},
    "RC_TONE_PERSUASIVE": {"family": "AuthorTone", "templates": ["What persuasive technique does the author employ?", "The author seeks to persuade the reader that:"]},
    "RC_TONE_OBJECTIVE": {"family": "AuthorTone", "templates": ["In what manner does the author present an objective account?", "The objective explanation emphasizes:"]},
    "RC_TONE_WHY_MENTION": {"family": "AuthorTone", "templates": ["Why does the author mention this specific point?", "The mention of this fact serves primarily to:"]},
    "RC_TONE_WHY_EXAMPLE": {"family": "AuthorTone", "templates": ["Why does the author provide the stated example?", "The example is used by the author to show that:"]},
    "RC_TONE_FUNCTION_SERVED": {"family": "AuthorTone", "templates": ["What function does this observation serve in the overall argument?", "In the context of the passage, this point functions as:"]},
    "RC_TONE_BEGIN_END": {"family": "AuthorTone", "templates": ["Why does the author begin/conclude the passage in this manner?", "The concluding remark highlights:"]},
    "RC_TONE_POSITION": {"family": "AuthorTone", "templates": ["What is the author's position regarding the development?", "The author firmly maintains that:"]},

    # Argument / Reasoning
    "RC_ARG_EVIDENCE": {"family": "Argument", "templates": ["What evidence does the author provide to support the claim?", "Which fact is cited as evidence in the passage?"]},
    "RC_ARG_CLAIM_EVIDENCE": {"family": "Argument", "templates": ["What is the relationship between the author's claim and the evidence provided?", "How does the evidence connect to the main claim?"]},
    "RC_ARG_CAUSE_EFFECT": {"family": "Argument", "templates": ["How does the author establish a cause-and-effect link?", "What causal relationship is asserted in the text?"]},
    "RC_ARG_PROBLEM_SOLUTION": {"family": "Argument", "templates": ["What solution does the author propose for the problem?", "The remedy suggested involves:"]},
    "RC_ARG_COMP_CONTRAST": {"family": "Argument", "templates": ["How does the comparison/contrast advance the argument?", "The author contrasts the two points in order to:"]},
    "RC_ARG_COUNTERARGUMENT": {"family": "Argument", "templates": ["What counterargument does the author address?", "Which opposing viewpoint is acknowledged in the text?"]},
    "RC_ARG_REBUTTAL": {"family": "Argument", "templates": ["How does the author rebut the counterargument?", "The author dismisses the objection by arguing that:"]},
    "RC_ARG_ASSUMPTION": {"family": "Argument", "templates": ["Which assumption is necessary for the author's argument to hold?", "The claim relies on the assumption that:"]},
    "RC_ARG_STRENGTHEN": {"family": "Argument", "templates": ["Which of the following, if true, would most STRENGTHEN the author's argument?", "The author's position would be fortified if:"]},
    "RC_ARG_WEAKEN": {"family": "Argument", "templates": ["Which of the following, if true, would most WEAKEN the author's argument?", "The author's conclusion is most vulnerable to which criticism?"]},
    "RC_ARG_LOGICAL_EXTENSION": {"family": "Argument", "templates": ["Which of the following represents a logical extension of the author's reasoning?", "Applying the author's logic elsewhere suggests that:"]},
    "RC_ARG_POLICY_IMPLIED": {"family": "Argument", "templates": ["What policy or action is implied by the passage?", "The author's arguments implicitly advocate for:"]},
    "RC_ARG_PREDICTED_OUTCOME": {"family": "Argument", "templates": ["What is the best predicted outcome based on the author's reasoning?", "The author would predict which future result?"]},
    "RC_ARG_RELATIONSHIP": {"family": "Argument", "templates": ["What is the relationship between the primary and secondary arguments in the passage?", "How does the author's second argument relate to the first?"]},
    "RC_ARG_PARA_FUNCTION": {"family": "Argument", "templates": ["What is the function of the specified paragraph in the passage?", "The specified paragraph primarily functions to:"]},

    # Vocabulary / Phrase / Reference
    "RC_VOCAB_CONTEXT_MEANING": {"family": "Vocabulary", "templates": ["What is the meaning of the highlighted word as used in the passage?", "In the context of the passage, the specified word refers to:"]},
    "RC_VOCAB_SYNONYM": {"family": "Vocabulary", "templates": ["Which word is the closest contextual SYNONYM to the highlighted word?", "Choose the word most similar in meaning in this context:"]},
    "RC_VOCAB_ANTONYM": {"family": "Vocabulary", "templates": ["Which word is the closest contextual ANTONYM to the highlighted word?", "Choose the word most opposite in meaning as used in the passage:"]},
    "RC_VOCAB_PHRASE": {"family": "Vocabulary", "templates": ["What is the meaning of the phrase as used in the passage?", "The highlighted phrase in the passage implies:"]},
    "RC_VOCAB_EXPRESSION": {"family": "Vocabulary", "templates": ["What does the highlighted expression convey in the text?", "The author uses the expression to indicate:"]},
    "RC_VOCAB_IDIOM": {"family": "Vocabulary", "templates": ["What is the meaning of the idiom in the context of the passage?", "The idiomatic usage means:"]},
    "RC_VOCAB_PHRASAL_VERB": {"family": "Vocabulary", "templates": ["What does the phrasal verb mean in the passage?", "In context, the phrasal verb signifies:"]},
    "RC_VOCAB_FIGURATIVE": {"family": "Vocabulary", "templates": ["What is the figurative meaning of the expression in the passage?", "Metaphorically, the expression represents:"]},
    "RC_VOCAB_LITERAL_VS_CONTEXT": {"family": "Vocabulary", "templates": ["How does the contextual meaning of the word differ from its literal definition?", "In this passage, the word is used to mean:"]},
    "RC_VOCAB_PRONOUN_REF": {"family": "Vocabulary", "templates": ["What does the highlighted pronoun in the paragraph refer to?", "The pronoun in the passage refers to:"]},
    "RC_VOCAB_HIGHLIGHT_REF": {"family": "Vocabulary", "templates": ["What is the reference of the highlighted expression?", "The highlighted text refers directly to:"]},
    "RC_VOCAB_DEMONSTRATIVE_REF": {"family": "Vocabulary", "templates": ["In the passage, what does 'this / that' refer to?", "The term refers to which preceding point?"]},
    "RC_VOCAB_SENTENCE_MEANING": {"family": "Vocabulary", "templates": ["What is the meaning of the highlighted sentence in context?", "The highlighted sentence implies that:"]},
    "RC_VOCAB_REPLACEMENT": {"family": "Vocabulary", "templates": ["Which word can best replace the highlighted word without changing the contextual meaning?", "The highlighted word can be replaced by:"]}
}

DISTRACTOR_MECHANISMS = [
    "partially_true_statement", "true_but_irrelevant", "scope_distortion",
    "opposite_of_passage", "exaggerated_claim", "under_generalisation",
    "over_generalisation", "causal_reversal", "correct_detail_wrong_conclusion",
    "close_contextual_near_synonym", "plausible_unsupported_inference",
    "fact_assigned_to_wrong_subject", "passage_fact_wrong_interpretation"
]

# =====================================================================
# 3. RC BLUEPRINT BANK (25 GENUINE BLUEPRINTS: 6-12 QUESTIONS)
# =====================================================================
RC_BLUEPRINTS = {
    # 6 Questions
    "RC_6Q_STANDARD": {"q_count": 6, "archetypes": ["RC_FACT_DIRECT_SUPPORT", "RC_MAIN_IDEA", "RC_VOCAB_SYNONYM", "RC_INF_CAN", "RC_TONE_OVERALL", "RC_FACT_DETAIL"]},
    "RC_6Q_INFERENCE_FOCUS": {"q_count": 6, "archetypes": ["RC_MAIN_ARGUMENT", "RC_INF_CAN", "RC_INF_IMPLICATION", "RC_VOCAB_CONTEXT_MEANING", "RC_INF_STRONGLY_SUPPORTED", "RC_TONE_STANCE"]},
    "RC_6Q_ARGUMENT_FOCUS": {"q_count": 6, "archetypes": ["RC_MAIN_IDEA", "RC_ARG_EVIDENCE", "RC_ARG_STRENGTHEN", "RC_ARG_WEAKEN", "RC_VOCAB_SYNONYM", "RC_INF_CAN"]},

    # 7 Questions
    "RC_7Q_FACT_HEAVY": {"q_count": 7, "archetypes": ["RC_FACT_TRUE", "RC_VOCAB_SYNONYM", "RC_INF_CAN", "RC_FACT_REASON", "RC_FACT_EFFECT", "RC_MAIN_IDEA", "RC_TONE_OVERALL"]},
    "RC_7Q_AUTHOR_ANALYSIS": {"q_count": 7, "archetypes": ["RC_TONE_PURPOSE", "RC_FACT_DETAIL", "RC_INF_CAN", "RC_VOCAB_PHRASE", "RC_TONE_ATTITUDE", "RC_ARG_PARA_FUNCTION", "RC_MAIN_IDEA"]},
    "RC_7Q_VOCAB_INFERENCE": {"q_count": 7, "archetypes": ["RC_VOCAB_CONTEXT_MEANING", "RC_INF_CAN", "RC_VOCAB_ANTONYM", "RC_FACT_DIRECT_SUPPORT", "RC_INF_IMPLICATION", "RC_VOCAB_REPLACEMENT", "RC_BEST_SUMMARY"]},
    "RC_7Q_STATEMENT_ANALYSIS": {"q_count": 7, "archetypes": ["RC_FACT_STATEMENTS_I_II_III", "RC_FACT_NOT_TRUE", "RC_INF_CAN", "RC_VOCAB_SYNONYM", "RC_FACT_COMBINATION", "RC_ARG_EVIDENCE", "RC_APPROPRIATE_TITLE"]},

    # 8 Questions
    "RC_8Q_BALANCED_TIER2": {"q_count": 8, "archetypes": ["RC_MAIN_IDEA", "RC_INF_CAN", "RC_VOCAB_CONTEXT_MEANING", "RC_TONE_PURPOSE", "RC_FACT_DIRECT_SUPPORT", "RC_TONE_OVERALL", "RC_INF_LIKELY_CONSEQUENCE", "RC_VOCAB_SYNONYM"]},
    "RC_8Q_INFERENCE_HEAVY": {"q_count": 8, "archetypes": ["RC_MAIN_ARGUMENT", "RC_INF_CAN", "RC_INF_IMPLICATION", "RC_FACT_DETAIL", "RC_INF_REASONABLE_ASSUMPTION", "RC_INF_STRONGLY_SUPPORTED", "RC_VOCAB_PHRASE", "RC_INF_CONCLUSION_FOLLOWS"]},
    "RC_8Q_ARGUMENT_APPLICATION": {"q_count": 8, "archetypes": ["RC_MAIN_IDEA", "RC_ARG_EVIDENCE", "RC_INF_CAN", "RC_ARG_STRENGTHEN", "RC_ARG_WEAKEN", "RC_ARG_POLICY_IMPLIED", "RC_VOCAB_SYNONYM", "RC_BEST_SUMMARY"]},
    "RC_8Q_FACT_AND_REFERENCE": {"q_count": 8, "archetypes": ["RC_FACT_TRUE", "RC_FACT_NOT_TRUE", "RC_VOCAB_PRONOUN_REF", "RC_INF_CAN", "RC_FACT_REASON", "RC_VOCAB_CONTEXT_MEANING", "RC_FACT_COMPARISON", "RC_APPROPRIATE_TITLE"]},

    # 9 Questions
    "RC_9Q_COMPREHENSIVE_MIX": {"q_count": 9, "archetypes": ["RC_VOCAB_CONTEXT_MEANING", "RC_FACT_DIRECT_SUPPORT", "RC_INF_CAN", "RC_FACT_DETAIL", "RC_TONE_OVERALL", "RC_MAIN_IDEA", "RC_INF_IMPLICATION", "RC_ARG_CAUSE_EFFECT", "RC_VOCAB_ANTONYM"]},
    "RC_9Q_BANKING_MAINS": {"q_count": 9, "archetypes": ["RC_MAIN_ARGUMENT", "RC_FACT_STATEMENTS_I_II_III", "RC_INF_CAN", "RC_ARG_ASSUMPTION", "RC_ARG_WEAKEN", "RC_VOCAB_PHRASE", "RC_INF_STRONGLY_SUPPORTED", "RC_TONE_STANCE", "RC_BEST_SUMMARY"]},
    "RC_9Q_CRITICAL_REASONING": {"q_count": 9, "archetypes": ["RC_MAIN_IDEA", "RC_ARG_EVIDENCE", "RC_ARG_COUNTERARGUMENT", "RC_ARG_REBUTTAL", "RC_INF_CAN", "RC_ARG_STRENGTHEN", "RC_VOCAB_SYNONYM", "RC_ARG_LOGICAL_EXTENSION", "RC_APPROPRIATE_TITLE"]},

    # 10 Questions
    "RC_10Q_TIER2_FULL": {"q_count": 10, "archetypes": ["RC_TONE_PURPOSE", "RC_FACT_DIRECT_SUPPORT", "RC_INF_CAN", "RC_VOCAB_CONTEXT_MEANING", "RC_ARG_POLICY_IMPLIED", "RC_FACT_DETAIL", "RC_INF_IMPLICATION", "RC_VOCAB_SYNONYM", "RC_TONE_OVERALL", "RC_MAIN_IDEA"]},
    "RC_10Q_INFERENCE_ANALYTICAL": {"q_count": 10, "archetypes": ["RC_MAIN_IDEA", "RC_INF_CAN", "RC_FACT_TRUE", "RC_INF_UNDERLYING_ASSUMPTION", "RC_VOCAB_PHRASE", "RC_ARG_CAUSE_EFFECT", "RC_INF_LIKELY_CONSEQUENCE", "RC_VOCAB_ANTONYM", "RC_INF_STRONGLY_SUPPORTED", "RC_BEST_SUMMARY"]},
    "RC_10Q_EDITORIAL_DEEP": {"q_count": 10, "archetypes": ["RC_APPROPRIATE_TITLE", "RC_FACT_REASON", "RC_FACT_EFFECT", "RC_VOCAB_CONTEXT_MEANING", "RC_INF_CAN", "RC_ARG_PARA_FUNCTION", "RC_TONE_ATTITUDE", "RC_ARG_STRENGTHEN", "RC_VOCAB_REPLACEMENT", "RC_OVERALL_MESSAGE"]},
    "RC_10Q_STATEMENT_EVIDENCE": {"q_count": 10, "archetypes": ["RC_FACT_STATEMENTS_I_II_III", "RC_FACT_DIRECT_SUPPORT", "RC_INF_CAN", "RC_ARG_EVIDENCE", "RC_VOCAB_SYNONYM", "RC_FACT_NOT_MENTIONED", "RC_INF_IMPLICATION", "RC_ARG_WEAKEN", "RC_VOCAB_HIGHLIGHT_REF", "RC_MAIN_ARGUMENT"]},

    # 11 Questions
    "RC_11Q_ADVANCED_MAINS": {"q_count": 11, "archetypes": ["RC_MAIN_IDEA", "RC_FACT_TRUE", "RC_INF_CAN", "RC_VOCAB_CONTEXT_MEANING", "RC_ARG_EVIDENCE", "RC_TONE_PURPOSE", "RC_INF_IMPLICATION", "RC_FACT_DETAIL", "RC_ARG_STRENGTHEN", "RC_VOCAB_ANTONYM", "RC_BEST_SUMMARY"]},
    "RC_11Q_REASONING_HEAVY": {"q_count": 11, "archetypes": ["RC_MAIN_ARGUMENT", "RC_INF_CAN", "RC_ARG_ASSUMPTION", "RC_FACT_STATEMENTS_I_II_III", "RC_VOCAB_PHRASE", "RC_ARG_WEAKEN", "RC_INF_STRONGLY_SUPPORTED", "RC_ARG_LOGICAL_EXTENSION", "RC_VOCAB_SYNONYM", "RC_TONE_OVERALL", "RC_APPROPRIATE_TITLE"]},

    # 12 Questions
    "RC_12Q_EXTENDED_EXAM": {"q_count": 12, "archetypes": ["RC_APPROPRIATE_TITLE", "RC_FACT_TRUE", "RC_FACT_NOT_TRUE", "RC_VOCAB_CONTEXT_MEANING", "RC_INF_CAN", "RC_TONE_PURPOSE", "RC_ARG_EVIDENCE", "RC_ARG_STRENGTHEN", "RC_ARG_WEAKEN", "RC_VOCAB_SYNONYM", "RC_INF_IMPLICATION", "RC_BEST_SUMMARY"]},
    "RC_12Q_MULTI_SKILL": {"q_count": 12, "archetypes": ["RC_MAIN_IDEA", "RC_FACT_DIRECT_SUPPORT", "RC_FACT_DETAIL", "RC_VOCAB_PRONOUN_REF", "RC_INF_CAN", "RC_ARG_CAUSE_EFFECT", "RC_TONE_ATTITUDE", "RC_INF_LIKELY_CONSEQUENCE", "RC_VOCAB_ANTONYM", "RC_ARG_POLICY_IMPLIED", "RC_FACT_COMBINATION", "RC_OVERALL_MESSAGE"]}
}

# =====================================================================
# 4. PARA JUMBLE BANKS
# =====================================================================
PJ_STRUCTURE_BANK = {
    "PJ_4S_FULL": {"sentence_count": 4, "format": "full_rearrangement", "fixed": None, "q_count": 1},
    "PJ_5S_FULL": {"sentence_count": 5, "format": "full_rearrangement", "fixed": None, "q_count": 1},
    "PJ_6S_FULL": {"sentence_count": 6, "format": "full_rearrangement", "fixed": None, "q_count": 1},
    "PJ_5S_FIXED_FIRST": {"sentence_count": 5, "format": "fixed_first", "fixed": {"label": "A", "pos": 1}, "q_count": 1},
    "PJ_5S_FIXED_LAST": {"sentence_count": 5, "format": "fixed_last", "fixed": {"label": "E", "pos": 5}, "q_count": 1},
    "PJ_6S_FIXED_FIRST": {"sentence_count": 6, "format": "fixed_first", "fixed": {"label": "A", "pos": 1}, "q_count": 1},
    "PJ_6S_FIXED_LAST": {"sentence_count": 6, "format": "fixed_last", "fixed": {"label": "F", "pos": 6}, "q_count": 1},
    "PJ_6S_SET_5Q": {"sentence_count": 6, "format": "sub_questions", "fixed": "dynamic", "q_count": 5}
}

PJ_LOGIC_BANK = [
    "General -> specific", "Specific -> generalisation", "Problem -> cause",
    "Problem -> consequence", "Problem -> solution", "Cause -> effect", "Effect -> cause",
    "Claim -> evidence", "Claim -> example", "Example -> conclusion", "Observation -> explanation",
    "Question -> answer", "Contrast", "Chronology", "Before -> change -> after",
    "Situation -> development -> result", "Issue -> response -> outcome"
]

PJ_LINKING_DEVICES = [
    "Pronoun reference", "Demonstrative reference", "Repeated key noun", "Synonym chain",
    "Definite article / prior reference", "Contrast marker", "Causal marker", "Result marker",
    "Addition marker", "Example marker", "Chronological marker"
]

# =====================================================================
# 5. CLOZE TEST BANKS
# =====================================================================
CLOZE_STRUCTURE_BANK = {
    "CLOZE_5B_GRAMMAR": {"blank_count": 5, "focus": "Grammar", "dependency": "local"},
    "CLOZE_5B_MIXED": {"blank_count": 5, "focus": "Mixed", "dependency": "mixed"},
    "CLOZE_6B_VOCAB": {"blank_count": 6, "focus": "Vocabulary", "dependency": "local"},
    "CLOZE_6B_MIXED": {"blank_count": 6, "focus": "Mixed", "dependency": "mixed"},
    "CLOZE_7B_REASONING": {"blank_count": 7, "focus": "Mixed Reasoning", "dependency": "paragraph"},
    "CLOZE_8B_MIXED": {"blank_count": 8, "focus": "Mixed Comprehensive", "dependency": "mixed"},
    "CLOZE_8B_LONG_RANGE": {"blank_count": 8, "focus": "Long Range Narrative", "dependency": "long-range"},
    "CLOZE_10B_EXTENDED": {"blank_count": 10, "focus": "Extended Editorial", "dependency": "long-range"}
}

CLOZE_CONCEPTS = {
    "Grammar": ["Tense", "Subject-verb agreement", "Article", "Determiner", "Preposition", "Conjunction", "Modal verb", "Parallel construction", "Pronoun case", "Verb form"],
    "Vocabulary": ["Contextual synonym", "Contextual antonym", "Collocation", "Verb-noun collocation", "Adjective-noun collocation", "Fixed expression", "Phrasal verb", "Shades of meaning"],
    "Logic": ["Cause marker", "Effect marker", "Contrast marker", "Concession marker", "Addition marker", "Example marker", "Result marker", "Condition marker"]
}

CLOZE_DEPENDENCY_MODELS = [
    "Local dependency (immediate sentence)",
    "Previous-sentence dependency",
    "Following-sentence dependency",
    "Paragraph-level dependency",
    "Long-range dependency",
    "Cross-blank dependency"
]

WU_TRAPS = [
    "Wrong semantic sense", "Wrong collocation", "Wrong preposition", "Wrong transitivity",
    "Wrong grammatical category", "Wrong complement pattern", "Wrong register",
    "Wrong idiomatic usage", "Confused near-synonym", "Contextually inappropriate usage"
]

# =====================================================================
# 6. MULTI-DIMENSIONAL PERSISTENT MEMORY ENGINE
# =====================================================================
MEMORY_WINDOWS = {
    "blueprint": 10,
    "structure": 15,
    "concept": 25,
    "wording": 15,
    "signatures": 10,
    "schedule": 6
}

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rc_blueprint_history": [],
        "rc_wording_history": [],
        "rc_signatures": [],
        "pj_blueprint_history": [],
        "pj_logic_history": [],
        "cloze_blueprint_history": [],
        "cloze_concept_history": [],
        "cloze_dependency_history": [],
        "wu_word_history": [],
        "wu_traps_history": [],
        "module_schedule_history": [],
        "recent_option_positions": []
    }

global_memory = load_memory()

def save_memory():
    for key, limit in MEMORY_WINDOWS.items():
        for hist_k in list(global_memory.keys()):
            if key in hist_k and isinstance(global_memory[hist_k], list):
                if len(global_memory[hist_k]) > limit:
                    global_memory[hist_k] = global_memory[hist_k][-limit:]
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(global_memory, f, indent=4)
    except Exception as e:
        log_audit("MEMORY_ERROR", f"Could not write to {MEMORY_FILE}: {e}")

def is_recent(history_key: str, value: str, window_limit: int = 15) -> bool:
    hist = global_memory.get(history_key, [])
    return value in hist[-window_limit:]

def record_memory(history_key: str, value):
    global_memory.setdefault(history_key, []).append(value)

def select_constrained_item(history_key: str, pool: list, window: int = 15) -> str:
    available = [item for item in pool if not is_recent(history_key, item, window)]
    if not available:
        available = pool
    chosen = random.choice(available)
    record_memory(history_key, chosen)
    return chosen

# =====================================================================
# 7. EDITORIAL LOADER (PRIVATE GITHUB API WITH FALLBACK)
# =====================================================================
GITHUB_OWNER = "prathu-developer"
GITHUB_REPO = "<SCRAPER-REPO-NAME>"  # Replace with your actual scraper repo name
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/today_editorials.json"

def get_hindu_editorials():
    log_audit("FETCH", "Retrieving daily editorials from private scraper repo...")
    raw_data = None

    if os.path.exists("today_editorials.json"):
        with open("today_editorials.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        token = os.environ.get("SCRAPER_REPO_PAT")
        headers = {
            "Accept": "application/vnd.github.raw",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.get(API_URL, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"GitHub API Error {resp.status_code}: {resp.text[:120]}")
        raw_data = resp.json()

    all_articles = raw_data.get("editorials", [])
    hindu = [a for a in all_articles if a.get("newspaper") == "The Hindu" and len(a.get("passage", "").strip()) > 300]
    express = [a for a in all_articles if a.get("newspaper") == "The Indian Express" and len(a.get("passage", "").strip()) > 300]

    chosen = (hindu + express)[:2]
    if len(chosen) < 2:
        raise ValueError(f"Expected 2 editorials, got {len(chosen)} (Hindu: {len(hindu)}, Express: {len(express)})")

    for art in chosen:
        log_audit("FETCH", f"Selected: [{art.get('newspaper')}] {art.get('title', '')[:50]}")

    return [
        {
            "title": item.get("title", "").strip(),
            "text": item.get("passage", "").strip(),
            "newspaper": item.get("newspaper", "")
        }
        for item in chosen
    ]

# =====================================================================
# 8. API CLIENT
# =====================================================================
def call_gemini_json(prompt: str, task_name: str) -> dict:
    max_retries = 3
    for attempt in range(max_retries):
        for model_name in MODELS:
            for i, key in enumerate(API_KEYS):
                if not key:
                    continue
                try:
                    log_audit("API_CALL", f"[{task_name}] {model_name} | Key {i+1} (Attempt {attempt+1})...")
                    client = genai.Client(api_key=key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            response_mime_type="application/json"
                        )
                    )
                    raw_text = getattr(response, "text", "") or ""
                    raw_text = raw_text.strip()

                    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    clean_json = match.group(0) if match else raw_text
                    return json.loads(clean_json)
                except Exception as e:
                    err_msg = str(e)
                    err_lower = err_msg.lower()
                    log_audit("API_FAIL", f"[{task_name}] {model_name} | Key {i+1} failed: {err_msg[:160]}")
                    if "429" in err_lower or "quota" in err_lower:
                        continue
                    elif "503" in err_lower or "unavailable" in err_lower or "overloaded" in err_lower:
                        time.sleep(3)
                        continue
                    else:
                        time.sleep(1)
    raise RuntimeError(f"API generation failed for task: {task_name}")

# =====================================================================
# 9. DETERMINISTIC PYTHON VALIDATOR & ANTI-STREAK OPTION SHUFFLER
# =====================================================================
def apply_anti_streak_option_shuffling(questions: list):
    """Randomizes option placement while preventing long answer streaks (e.g. A,A,A or cycles)."""
    alphabet = ["A", "B", "C", "D"]
    recent_answers = global_memory.get("recent_option_positions", [])
    
    for q in questions:
        options = q["options"]
        correct = q["correct_answer"]
        
        shuffled = options.copy()
        random.shuffle(shuffled)
        
        corr_idx = shuffled.index(correct)
        corr_pos = alphabet[corr_idx]
        
        if len(recent_answers) >= 2 and recent_answers[-1] == corr_pos and recent_answers[-2] == corr_pos:
            alt_indices = [idx for idx in range(len(shuffled)) if idx != corr_idx]
            swap_idx = random.choice(alt_indices)
            shuffled[corr_idx], shuffled[swap_idx] = shuffled[swap_idx], shuffled[corr_idx]
            corr_idx = swap_idx
            corr_pos = alphabet[corr_idx]
            
        q["options"] = shuffled
        recent_answers.append(corr_pos)
        
    global_memory["recent_option_positions"] = recent_answers[-30:]

def python_deterministic_qa(set_type: str, data: dict, expected_count: int):
    """Rigorous Python deterministic validation and sanitization maintaining exact schema."""
    if not isinstance(data, dict): return False, "Output is not a valid JSON object.", data
    if "questions" not in data or not isinstance(data["questions"], list): return False, "Missing 'questions' list.", data
    
    questions = data["questions"]
    if len(questions) != expected_count:
        return False, f"Expected {expected_count} questions, got {len(questions)}.", data

    prefix_re = re.compile(r"^[\(]?[A-Ea-e][\)\.\:\-]\s*", re.IGNORECASE)
    forbidden_terms = ["option a", "option b", "option c", "option d", "first option", "second option", "third option", "fourth option"]

    for i, q in enumerate(questions):
        raw_opts = q.get("options", [])
        if isinstance(raw_opts, dict): raw_opts = list(raw_opts.values())
        if len(raw_opts) != 4: return False, f"Q{i+1} does not have exactly 4 options.", data
        
        clean_opts = [prefix_re.sub("", str(opt)).strip() for opt in raw_opts]
        if len(set(clean_opts)) != 4: return False, f"Q{i+1} has duplicate options after stripping.", data
        q["options"] = clean_opts
        
        clean_ans = prefix_re.sub("", str(q.get("correct_answer", ""))).strip()
        if clean_ans not in clean_opts:
            for opt in clean_opts:
                if clean_ans.lower() == opt.lower():
                    clean_ans = opt
                    break
            else:
                return False, f"Q{i+1} correct_answer '{clean_ans}' does not match any option.", data
        q["correct_answer"] = clean_ans
        
        explanation = q.get("explanation", "")
        # Remove any lingering "Option A/B/C/D" labels so the explanation remains accurate after shuffle
        explanation = re.sub(r"\bOption\s+[A-Da-d][:\-\s]*", "", explanation, flags=re.IGNORECASE)
        q["explanation"] = explanation.strip()

    if set_type == "Cloze Test":
        passage = data.get("passage", "")
        for b in range(1, expected_count + 1):
            if passage.count(f"({b})") != 1:
                return False, f"Cloze passage must contain exactly one instance of blank ({b}).", data

    if set_type == "Para Jumbles":
        if "correct_sequence" not in data or not isinstance(data["correct_sequence"], list):
            return False, "Missing 'correct_sequence' list.", data
        for q in questions:
            if "sentences" not in q or not isinstance(q["sentences"], dict):
                return False, "Missing 'sentences' dictionary inside question object.", data

    apply_anti_streak_option_shuffling(questions)
    return True, "QA passed.", data

# =====================================================================
# 10. GENERATION MODULES (EXACT ORIGINAL SCHEMA COMPLIANT)
# =====================================================================
def generate_rc_module(editorial_text: str):
    bp_id = select_constrained_item("rc_blueprint_history", list(RC_BLUEPRINTS.keys()), MEMORY_WINDOWS["blueprint"])
    bp = RC_BLUEPRINTS[bp_id]
    
    slot_archetypes = bp["archetypes"]
    compiled_slots = []
    for i, arch in enumerate(slot_archetypes):
        arch_data = RC_STRUCTURE_BANK[arch]
        wording = select_constrained_item("rc_wording_history", arch_data["templates"], MEMORY_WINDOWS["wording"])
        distractor_trap = random.choice(DISTRACTOR_MECHANISMS)
        compiled_slots.append({
            "slot_id": f"Q{i+1}",
            "archetype_id": arch,
            "family": arch_data["family"],
            "wording_template": wording,
            "target_distractor_mechanism": distractor_trap
        })

    prompt = f"""[ROLE] Senior Question Setter for SSC CGL Tier-II & Banking Mains.
[TASK] Create a Reading Comprehension test following this exact structural blueprint.
[SOURCE EDITORIAL]
{editorial_text}

[BLUEPRINT: {bp_id} | Total Questions: {bp['q_count']}]
{json.dumps(compiled_slots, indent=2)}

[RULES]
1. Extract a continuous 500-800 word passage from the editorial. Keep exact wording.
2. Formulate each question using the exact slot archetype and wording template assigned.
3. Construct 4 distinct options per question. Build wrong choices using the assigned distractor mechanisms.
4. Source-Bound: Every correct answer and explanation must rely strictly on passage logic.
5. NO 'A.', 'B.', 'C.', 'D.' prefixes in options.
6. EXPLANATION FORMAT: Options are shuffled randomly for students. Never refer to option letters (A, B, C, D) or positions. Quote the option text directly:
   **Why '<correct_answer>' is correct:** [1-2 concise sentences showing passage proof]
   **Why other options are incorrect:**
   • '<distractor 1 text>': [1 sentence showing why it is wrong]
   • '<distractor 2 text>': [1 sentence showing why it is wrong]
   • '<distractor 3 text>': [1 sentence showing why it is wrong]

[EXACT JSON OUTPUT FORMAT]
{{
  "type": "reading_comprehension",
  "instruction": "Directions: Read the following passage carefully and answer the questions given below.",
  "passage": "...",
  "questions": [
    {{
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "**Why '...' is correct:** ...\\n\\n**Why other options are incorrect:**\\n• '...': ...\\n• '...': ...\\n• '...': ..."
    }}
  ]
}}"""
    raw = call_gemini_json(prompt, f"RC-{bp_id}")
    valid, msg, cleaned = python_deterministic_qa("Reading Comprehension", raw, bp["q_count"])
    if not valid:
        log_audit("QA_FAIL", f"RC validation failed: {msg}")
        return None

    return cleaned

def generate_pj_module(inspiration_text: str):
    bp_id = select_constrained_item("pj_blueprint_history", list(PJ_STRUCTURE_BANK.keys()), MEMORY_WINDOWS["blueprint"])
    bp = PJ_STRUCTURE_BANK[bp_id]
    logic_rel = select_constrained_item("pj_logic_history", PJ_LOGIC_BANK, MEMORY_WINDOWS["concept"])
    link_dev = select_constrained_item("pj_logic_history", PJ_LINKING_DEVICES, MEMORY_WINDOWS["concept"])

    dynamic_fixed_label = random.choice(["A", "B", "C", "D", "E", "F"][:bp["sentence_count"]])
    dynamic_fixed_pos = random.randint(1, bp["sentence_count"])

    fixed_sentence = dynamic_fixed_label if bp.get("fixed") == "dynamic" else (bp.get("fixed", {}).get("label") if bp.get("fixed") else "A")
    fixed_position = dynamic_fixed_pos if bp.get("fixed") == "dynamic" else (bp.get("fixed", {}).get("pos") if bp.get("fixed") else 1)

    instruction_text = f"Directions: Six sentences are given below. Sentence {fixed_sentence} is fixed at position {fixed_position}. Rearrange the remaining sentences to form a meaningful paragraph and answer the questions." if bp["sentence_count"] == 6 and bp["q_count"] > 1 else "Directions: The following sentences when properly sequenced form a coherent paragraph. Each sentence is labelled with a letter. Choose the most logical order."

    prompt = f"""[ROLE] Elite Exam Paper Setter.
[TASK] Construct a Para Jumble module matching Blueprint {bp_id}.
[SOURCE THEME]
{inspiration_text}

[STRUCTURAL CONSTRAINTS]
- Sentence Count: {bp['sentence_count']}
- Target Structure: {logic_rel}
- Linking Device: {link_dev}
- Format: {bp['format']}
- Questions count: {bp['q_count']}
- Fixed Sentence: {fixed_sentence} at position {fixed_position}

[RULES]
1. Write {bp['sentence_count']} coherent sentences labeled A, B, C, D, ...
2. Provide 'correct_sequence' as an array of letters (e.g., ["C", "A", "D", "B", "E", "F"]). Position {fixed_position} MUST be sentence {fixed_sentence}.
3. Include the full 'sentences' dictionary inside EVERY question object.
4. Exactly 4 flat string options per question. No letter prefixes.
5. EXPLANATION FORMAT: Options are shuffled. Explain the link for the correct choice first, then state why the remaining choices fail:
   **Why '<correct_answer>' is correct:** [Logical link or transition evidence]
   **Why other options are incorrect:**
   • '<wrong choice 1>': [Reason it fails cohesion]
   • '<wrong choice 2>': [Reason it fails cohesion]
   • '<wrong choice 3>': [Reason it fails cohesion]

[EXACT JSON OUTPUT FORMAT]
{{
  "type": "para_jumbles",
  "instruction": "{instruction_text}",
  "fixed_sentence": "{fixed_sentence}",
  "fixed_position": {fixed_position},
  "correct_sequence": ["...", "..."],
  "questions": [
    {{
      "sentences": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "...", "F": "..."}},
      "question": "Which sentence should come immediately after Sentence X?",
      "options": ["B", "C", "D", "E"],
      "correct_answer": "C",
      "explanation": "..."
    }}
  ]
}}"""
    raw = call_gemini_json(prompt, f"PJ-{bp_id}")
    valid, msg, cleaned = python_deterministic_qa("Para Jumbles", raw, bp["q_count"])
    if not valid:
        log_audit("QA_FAIL", f"PJ validation failed: {msg}")
        return None

    return cleaned

def generate_cloze_module(editorial_text: str):
    bp_id = select_constrained_item("cloze_blueprint_history", list(CLOZE_STRUCTURE_BANK.keys()), MEMORY_WINDOWS["blueprint"])
    bp = CLOZE_STRUCTURE_BANK[bp_id]
    dep_model = select_constrained_item("cloze_dependency_history", CLOZE_DEPENDENCY_MODELS, MEMORY_WINDOWS["structure"])

    compiled_blanks = []
    for b in range(1, bp["blank_count"] + 1):
        if bp["focus"] == "Grammar": cat = "Grammar"
        elif bp["focus"] == "Vocabulary": cat = "Vocabulary"
        else: cat = random.choice(["Grammar", "Vocabulary", "Logic"])
        concept = select_constrained_item("cloze_concept_history", CLOZE_CONCEPTS[cat], MEMORY_WINDOWS["concept"])
        compiled_blanks.append({"blank_id": f"({b})", "category": cat, "concept": concept})

    prompt = f"""[ROLE] Elite Exam Paper Setter.
[TASK] Construct a Cloze Test matching Blueprint {bp_id}.
[SOURCE EDITORIAL]
{editorial_text}

[SPECIFICATIONS]
- Blanks Count: {bp['blank_count']}
- Dependency Model: {dep_model}
- Blank Concepts: {json.dumps(compiled_blanks, indent=2)}

[RULES]
1. Extract a 180-280 word passage from the text and insert exactly {bp['blank_count']} blanks labeled (1), (2), ... ({bp['blank_count']}).
2. Create exactly {bp['blank_count']} multiple choice questions. Question text: "Q1. (1) ______", "Q2. (2) ______", etc.
3. Distractors must be contextually challenging and plausible.
4. No 'A.', 'B.' prefixes in option strings.
5. EXPLANATION FORMAT: Options are shuffled. Do not use option letters (A, B, C, D). Quote the actual words:
   **Why '<correct_answer>' is correct:** [Meaning and why it fits contextually]
   **Why other options are incorrect:**
   • '<distractor 1>': [Why it fails]
   • '<distractor 2>': [Why it fails]
   • '<distractor 3>': [Why it fails]

[EXACT JSON OUTPUT FORMAT]
{{
  "type": "cloze_test",
  "instruction": "Directions: In the following passage, there are blanks labeled (1), (2)... Read the passage carefully and choose the correct option for each blank.",
  "passage": "Passage text with (1) ... (2) ...",
  "questions": [
    {{
      "question": "Q1. (1) ______",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "..."
    }}
  ]
}}"""
    raw = call_gemini_json(prompt, f"Cloze-{bp_id}")
    valid, msg, cleaned = python_deterministic_qa("Cloze Test", raw, bp["blank_count"])
    if not valid:
        log_audit("QA_FAIL", f"Cloze validation failed: {msg}")
        return None

    return cleaned

def generate_word_usage_module(editorial_text: str):
    traps = [select_constrained_item("wu_traps_history", WU_TRAPS, 10) for _ in range(5)]
    prompt = f"""[ROLE] Elite Exam Paper Setter.
[TASK] Select 5 advanced Tier-II vocabulary words from the text and create Word Usage questions.
[SOURCE TEXT]
{editorial_text}

[TARGET DISTRACTOR TRAPS]
{json.dumps(traps, indent=2)}

[RULES]
1. Select 5 distinct Tier-II vocabulary words.
2. For each word, create 4 natural sentences using the word. Exactly ONE sentence must be correct in both semantics and syntax.
3. The other 3 sentences must fail based on the assigned traps.
4. Question text must simply be the TARGET WORD in uppercase.
5. EXPLANATION FORMAT: Options are shuffled. Do not use option letters:
   **Why this sentence is correct:** [Precise meaning and grammatical/collocational fit]
   **Why other sentences are incorrect:**
   • '<Snippet of incorrect sentence 1>': [Identify the trap/error]
   • '<Snippet of incorrect sentence 2>': [Identify the trap/error]
   • '<Snippet of incorrect sentence 3>': [Identify the trap/error]

[EXACT JSON OUTPUT FORMAT]
{{
  "type": "word_usage",
  "instruction": "Directions: Choose the sentence in which the given word is used correctly with respect to both grammar and contextual meaning.",
  "questions": [
    {{
      "question": "TARGET_WORD",
      "options": ["Sentence 1...", "Sentence 2...", "Sentence 3...", "Sentence 4..."],
      "correct_answer": "Sentence X...",
      "explanation": "..."
    }}
  ]
}}"""
    raw = call_gemini_json(prompt, "WordUsage-5Q")
    valid, msg, cleaned = python_deterministic_qa("Word Usage", raw, 5)
    if not valid:
        log_audit("QA_FAIL", f"Word Usage validation failed: {msg}")
        return None

    for q in cleaned["questions"]:
        w = q.get("question", "").strip().upper()
        record_memory("wu_word_history", w)
        q["question"] = w

    return cleaned

# =====================================================================
# 11. MAIN ORCHESTRATOR & PERSISTENCE
# =====================================================================
def main():
    log_audit("START", "🚀 Initializing Comprehension Pipeline with Exact Original Schema Contract...")
    
    current_day = datetime.now().weekday()
    if current_day == 6: # Sunday off
        log_audit("SCHEDULE", "Sunday - Generation paused.")
        return

    editorials = get_hindu_editorials()
    if len(editorials) < 2:
        log_audit("ERROR", "Failed to retrieve 2 distinct editorials.")
        sys.exit(1)

    ed1_text = editorials[0]['text']
    ed2_text = editorials[1]['text']

    final_output = {"date": datetime.now().strftime("%Y-%m-%d")}

    # SET D: READING COMPREHENSION (Mon=0, Thu=3)
    if current_day in [0, 3]:
        try:
            res_d = generate_rc_module(ed1_text)
            if res_d:
                final_output["set_d"] = res_d
        except Exception as e:
            log_audit("MODULE_ERROR", f"Set D generation failed: {e}")
        time.sleep(5)

    # SET F: PARA JUMBLES (Tue=1, Fri=4)
    if current_day in [1, 4]:
        try:
            res_f = generate_pj_module(ed2_text)
            if res_f:
                final_output["set_f"] = res_f
        except Exception as e:
            log_audit("MODULE_ERROR", f"Set F generation failed: {e}")
        time.sleep(5)

    # SET E: CLOZE TEST (Wed=2, Sat=5)
    if current_day in [2, 5]:
        try:
            res_e = generate_cloze_module(ed2_text)
            if res_e:
                final_output["set_e"] = res_e
        except Exception as e:
            log_audit("MODULE_ERROR", f"Set E generation failed: {e}")
        time.sleep(5)

    # SET G: WORD USAGE (Tue=1, Wed=2, Fri=4, Sat=5)
    if current_day in [1, 2, 4, 5]:
        try:
            res_g = generate_word_usage_module(ed1_text)
            if res_g:
                final_output["set_g"] = res_g
        except Exception as e:
            log_audit("MODULE_ERROR", f"Set G generation failed: {e}")

    # SAVE FINAL OUTPUT & MEMORY (EXACT ORIGINAL STRUCTURE)
    if len(final_output) > 1:
        with open("comprehension_tests.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4)
        save_memory()
        log_audit("COMPLETE", "🎉 QA-validated sets saved in exact original format, and novelty memory committed.")
    else:
        log_audit("ERROR", "No valid test modules succeeded today.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_audit("CRITICAL", str(e))
        if BOT_TOKEN and ADMIN_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"🚨 **COMPREHENSION ENGINE CRITICAL ERROR:**\n`{e}`",
                "parse_mode": "Markdown"
            })
        sys.exit(1)
