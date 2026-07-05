import os
from google import genai

# Securely fetch the API key from the GitHub Actions environment
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("CRITICAL: GEMINI_API_KEY environment variable not set.")
    exit(1)

# Pass the key to the Gemini client
client = genai.Client(api_key=api_key)
