import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET
from readability import Document

def scrape_hindu_editorials():
    rss_url = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    resp = requests.get(rss_url, headers=headers)
    root = ET.fromstring(resp.content)
    
    editorials = []
    items = root.findall('.//item')[:2]
    
    for item in items:
        title = item.find('title').text
        link = item.find('link').text
        
        # 1. Fetch the raw webpage
        page_resp = requests.get(link, headers=headers)
        
        # 2. 🔥 ACTIVATE BROWSER "READER MODE" 🔥
        # This automatically identifies the main article and deletes all sidebars, paywalls, and menus!
        doc = Document(page_resp.text)
        reader_mode_html = doc.summary() 
        
        # 3. Use BeautifulSoup to remove the remaining HTML tags, leaving only pure text
        soup = BeautifulSoup(reader_mode_html, 'html.parser')
        full_text = soup.get_text(separator='\n', strip=True)
        
        editorials.append({
            "title": title,
            "text": full_text
        })
        
    with open('editorials.json', 'w', encoding='utf-8') as f:
        json.dump(editorials, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_hindu_editorials()
    print("Successfully scraped editorials using Reader Mode!")
