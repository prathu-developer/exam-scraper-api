import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET
import re

def scrape_hindu_editorials():
    rss_url = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"
    # We use a browser header so The Hindu's website doesn't block GitHub's automated request
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    resp = requests.get(rss_url, headers=headers)
    root = ET.fromstring(resp.content)
    
    editorials = []
    items = root.findall('.//item')[:2]
    
    # List of exact phrases we want to instantly delete if the scraper catches them
    junk_phrases = [
        "You don’t have any Active Subscription",
        "Subscribed with another email?",
        "Logout and Login with that one",
        "Account subscription benefits",
        "Premium Stories, Editorials",
        "Unlock these with Subscription",
        "Additional Subscription Benefits",
        "Need help with your subscription?",
        "The View From India",
        "Looking at World Affairs",
        "First Day First Show",
        "News and reviews from the world of cinema",
        "Today's Cache",
        "Your download of the top 5 technology stories",
        "Science For All",
        "The weekly newsletter from science writers",
        "takes the jargon out of science",
        "Data Point",
        "Decoding the headlines",
        "THEdge",
        "At the cutting edge of education",
        "Health Matters",
        "Ramya Kannan writes to you",
        "getting to good health",
        "Gender Agenda",
        "Stories from beyond the binary",
        "The Hindu On Books",
        "Books of the week",
        "Comments have to be in English",
        "They cannot be abusive or personal",
        "abide by ourcommunity guidelines",
        "We have migrated to a new commenting platform",
        "If you are already a registered user",
        "If you do not have an account please register",
        "Users can access their older comments",
        "THG PUBLISHING PVT LTD",
        "All rights reserved"
    ]
    
    for item in items:
        title = item.find('title').text
        link = item.find('link').text
        
        page_resp = requests.get(link, headers=headers)
        soup = BeautifulSoup(page_resp.content, 'html.parser')
        
        # 1. Try to find the actual article body to avoid the sidebar completely
        article_body = soup.find('div', itemprop='articleBody')
        if not article_body:
            article_body = soup
            
        paragraphs = article_body.find_all('p')
        
        clean_paragraphs = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            
            # Skip completely empty or tiny paragraphs
            if len(text) < 30:
                continue
                
            # Check if this paragraph contains any of our known garbage phrases
            is_junk = False
            for junk in junk_phrases:
                if junk.lower() in text.lower():
                    is_junk = True
                    break
                    
            if not is_junk:
                clean_paragraphs.append(text)
        
        full_text = " ".join(clean_paragraphs)
        
        # 2. Final Sweep: Remove the "Updated - ... IST" and "Published - ... IST" date stamps
        full_text = re.sub(r'Updated\s*-\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+\d{2}:\d{2}\s+[ap]m\s+IST', '', full_text, flags=re.IGNORECASE)
        full_text = re.sub(r'Published\s*-\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+\d{2}:\d{2}\s+[ap]m\s+IST', '', full_text, flags=re.IGNORECASE)
        
        editorials.append({
            "title": title,
            "text": full_text.strip()
        })
        
    with open('editorials.json', 'w', encoding='utf-8') as f:
        json.dump(editorials, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_hindu_editorials()
    print("Successfully scraped and CLEANED full editorials!")
