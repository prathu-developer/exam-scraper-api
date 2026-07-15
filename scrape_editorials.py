import requests
from bs4 import BeautifulSoup
import json
import xml.etree.ElementTree as ET

def scrape_hindu_editorials():
    rss_url = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"
    # We use a browser header so The Hindu's website doesn't block GitHub's automated request
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    # 1. Fetch the RSS feed just to get the URLs
    resp = requests.get(rss_url, headers=headers)
    root = ET.fromstring(resp.content)
    
    editorials = []
    # Grab the top 2 latest articles
    items = root.findall('.//item')[:2]
    
    for item in items:
        title = item.find('title').text
        link = item.find('link').text
        
        # 2. Visit the actual web page and scrape the full text
        page_resp = requests.get(link, headers=headers)
        soup = BeautifulSoup(page_resp.content, 'html.parser')
        
        # Extract all paragraph text, ignoring tiny UI elements
        paragraphs = soup.find_all('p')
        full_text = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])
        
        editorials.append({
            "title": title,
            "text": full_text
        })
        
    # 3. Save the massive text block into a JSON file
    with open('editorials.json', 'w', encoding='utf-8') as f:
        json.dump(editorials, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_hindu_editorials()
    print("Successfully scraped full editorials!")
