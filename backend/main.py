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
from newspaper import Article
import re

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app-news-summarizer.onrender.com"], 
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

def extract_main_article_text(url: str) -> Dict:
    """
    Fetches the content of a given URL and attempts to extract the main article text,
    title, and link using newspaper3k.
    """
    try:
        article = Article(url)
        
        article.download()
        article.parse()
        
        # Build the article object to return
        extracted_data = {
            "title": article.title if article.title else "No Title Found",
            "text": article.text if article.text else "Could not extract meaningful content from the URL.",
            "link": url 
        }
        
        if len(extracted_data["text"].strip()) < 100:
            extracted_data["text"] = "Could not extract meaningful content from the URL."
            
        return extracted_data

    except Exception as e:
        print(f"Error extracting article with newspaper3k from {url}: {e}")
        error_message = f"Error extracting article content: {e}. The website might be blocking automated access or has a complex structure."
        return {
            "title": "Extraction Error",
            "text": error_message,
            "link": url
        }


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

    extracted_article_data = extract_main_article_text(request.article_url)
    
    if "Error extracting article content" in extracted_article_data["text"] or \
       "Could not extract meaningful content" in extracted_article_data["text"]:
        raise HTTPException(status_code=400, detail=extracted_article_data["text"])
    
    # Summarize the extracted text
    summary = summarize_article_content(extracted_article_data["text"])

    print(f"Successfully summarized single article: {request.article_url}")
    return {
        "message": "Article summary generated successfully!",
        "summaries": [{
            "title": extracted_article_data["title"],
            "link": extracted_article_data["link"],
            "summary": summary
        }]
    }
