import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence

import feedparser
import requests
from bs4 import BeautifulSoup
import re

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it in a .env file.")

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7, google_api_key=GOOGLE_API_KEY)

summarization_prompt = PromptTemplate(
    input_variables=["text"],
    template="""Summarize the following news article concisely and clearly. 
    Focus on the main points and key information. 
    Keep the summary to a maximum of 3-5 sentences.

    Article:
    {text}

    Summary:
    """
)

summarization_chain = summarization_prompt | llm

class SummarizeRSSRequest(BaseModel):
    rss_url: str
    num_articles: int = 5

class SummarizeArticleRequest(BaseModel):
    article_url: str

def summarize_article_content(article_text: str) -> str:
    if not article_text or len(article_text.strip()) < 50:
        return "Content too short or empty to summarize."
    
    try:
        response = summarization_chain.invoke({"text": article_text})
        summary = response.content
        return summary.strip()
    except Exception as e:
        print(f"Error during summarization: {e}")
        return f"Failed to generate summary due to an AI error: {e}"

def fetch_news_from_rss(rss_url: str, num_articles: int = 5) -> List[Dict]:
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries[:num_articles]:
            title = getattr(entry, 'title', "No Title")
            link = getattr(entry, 'link', "No Link")
            content = getattr(entry, 'summary_detail', {}).get('value', '') or \
                      getattr(entry, 'summary', '') or \
                      getattr(entry, 'description', '')
            
            articles.append({
                "title": title,
                "link": link,
                "content": content
            })
        return articles
    except Exception as e:
        print(f"Error fetching RSS feed {rss_url}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch RSS feed: {e}")

def extract_main_article_text(url: str) -> str:
    """
    Fetches the content of a given URL and attempts to extract the main article text.
    This is a heuristic and may not work perfectly for all websites, especially those
    heavily reliant on client-side JavaScript rendering.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1', # Do Not Track
        }
        
        if "google.com" in url or "bing.com" in url: 
            headers['Referer'] = 'https://www.google.com/'
        else:
             headers['Referer'] = url # Self-refer if not from a search engine

        response = requests.get(url, headers=headers, timeout=15) # Increased timeout
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')

        # Prioritized selectors for main article content
        # Ordered from most specific/reliable to more generic
        selectors = [
            'article[itemprop="articleBody"]', # Common for many news sites
            'div[itemprop="articleBody"]',
            'article.post-content',
            'div.post-content',
            'div.entry-content',
            'div.article-body',
            'div.article__content',
            'div.g-article', # Specific to some Google News articles
            'article', # General article tag
            'main',    # General main content tag
            'div[role="main"]',
            '#main-content',
            '#article-content',
            '#main',
            '#content',
        ]

        article_text_parts = []
        for selector in selectors:
            found_element = soup.select_one(selector)
            if found_element:
                # Extract all paragraph text within the found element
                paragraphs = found_element.find_all('p')
                if paragraphs:
                    # Filter out very short paragraphs (e.g., captions, empty)
                    # and join them. Min length increased slightly.
                    text = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    if text: # Ensure we actually extracted some text
                        article_text_parts.append(text)
                        break # Stop after finding the first good content block

        full_text = "\n\n".join(article_text_parts)
        
        # Fallback: If no specific article content found, try to get all text from body or common divs
        if not full_text or len(full_text.strip()) < 100: # If initial extraction failed or too short
            body_text = []
            for p in soup.find_all('p'):
                p_text = p.get_text(strip=True)
                if len(p_text) > 50 and not p_text.lower().startswith(('read more', 'comments', 'share this')): # Basic filter for boilerplate
                    body_text.append(p_text)
            full_text = "\n\n".join(body_text)

        # Further clean up common web artifacts (e.g., multiple newlines, script tags text)
        full_text = re.sub(r'\s+', ' ', full_text).strip() # Replace multiple spaces/newlines with single space
        
        return full_text if len(full_text) > 100 else "Could not extract meaningful content from the URL."

    except requests.exceptions.RequestException as e:
        print(f"Network or HTTP error fetching {url}: {e}")
        # Return a more specific error message from the HTTP status code
        if response.status_code == 404:
            return f"Error fetching article from URL: 404 Not Found. The article might not exist or the URL is incorrect."
        elif response.status_code == 403:
            return f"Error fetching article from URL: 403 Forbidden. The website might be blocking automated access."
        else:
            return f"Error fetching article from URL: {e}"
    except Exception as e:
        print(f"Error parsing content from {url}: {e}")
        return f"Error processing article content: {e}"

@app.get("/")
async def read_root():
    return {"message": "Daily News Summarizer API is running!"}

@app.post("/summarize_rss")
async def summarize_rss_endpoint(request: SummarizeRSSRequest):
    print(f"Received RSS request to summarize {request.num_articles} articles from: {request.rss_url}")
    
    articles_data = fetch_news_from_rss(request.rss_url, request.num_articles)
    
    if not articles_data:
        return {"message": "No articles found or fetched from the provided RSS feed.", "summaries": []}

    summarized_articles = []
    for article in articles_data:
        summary = summarize_article_content(article['content'])
        summarized_articles.append({
            "title": article['title'],
            "link": article['link'],
            "summary": summary
        })
    
    print(f"Successfully summarized {len(summarized_articles)} RSS articles.")
    return {"message": "RSS Summaries generated successfully!", "summaries": summarized_articles}

@app.post("/summarize_article")
async def summarize_single_article_endpoint(request: SummarizeArticleRequest):
    print(f"Received request to summarize single article from: {request.article_url}")

    # Extract full text from the article URL
    article_full_text = extract_main_article_text(request.article_url)

    # Check for specific error messages from extract_main_article_text
    if "Error fetching" in article_full_text or "Could not extract" in article_full_text:
        # If it's a specific error message, raise HTTPException with it
        raise HTTPException(status_code=400, detail=article_full_text)
    
    # Summarize the extracted text
    summary = summarize_article_content(article_full_text)

    title = f"Summary of: {request.article_url}"

    try:
        # Try to get title from the fetched HTML
        response = requests.get(request.article_url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        html_title = soup.find('title')
        if html_title and html_title.string:
            title = html_title.string.strip()
    except Exception as e:
        print(f"Could not extract title from URL: {e}")


    print(f"Successfully summarized single article: {request.article_url}")
    return {
        "message": "Article summary generated successfully!",
        "summaries": [{
            "title": title,
            "link": request.article_url,
            "summary": summary
        }]
    }
