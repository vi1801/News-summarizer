import React, { useState } from 'react';
import './App.css'; // Import the CSS file

const BackendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8888';

function App() {
  // State for RSS summarization
  const [rssUrl, setRssUrl] = useState('');
  const [numArticles, setNumArticles] = useState(3);

  // State for Single Article summarization
  const [articleUrl, setArticleUrl] = useState('');

  // Common states for results and loading
  const [summaries, setSummaries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState('');

  const resetState = () => {
    setSummaries([]);
    setError(null);
    setMessage('');
  };

  // Handler for RSS summarization
  const handleSummarizeRSS = async (e) => {
    e.preventDefault();
    resetState();
    setLoading(true);

    if (!rssUrl) {
      setError("Please enter an RSS Feed URL.");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${BackendUrl}/summarize_rss`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rss_url: rssUrl, num_articles: numArticles }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch RSS summaries.');
      }

      const data = await response.json();
      setSummaries(data.summaries);
      setMessage(data.message);

    } catch (err) {
      console.error('Error:', err);
      setError(`Error: ${err.message}. Please check the RSS URL and ensure the backend is running.`);
    } finally {
      setLoading(false);
    }
  };

  // Handler for Single Article summarization
  const handleSummarizeArticle = async (e) => {
    e.preventDefault();
    resetState();
    setLoading(true);

    if (!articleUrl) {
      setError("Please enter an Article URL.");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${BackendUrl}/summarize_article`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ article_url: articleUrl }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch article summary.');
      }

      const data = await response.json();
      setSummaries(data.summaries); // This will be an array with one summary
      setMessage(data.message);

    } catch (err) {
      console.error('Error:', err);
      setError(`Error: ${err.message}. Please check the Article URL and ensure the backend is running.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="card">
        <h1 className="title">Daily News Summarizer Bot</h1>
        <p className="description">
          Get concise summaries from RSS feeds or individual news article URLs.
        </p>

        {/* RSS Summarization Section */}
        <div className="summarization-section">
          <h2 className="section-heading">Summarize from RSS Feed</h2>
          <form onSubmit={handleSummarizeRSS} className="form-section">
            <div className="input-group">
              <label htmlFor="rss-url" className="label">RSS Feed URL:</label>
              <input
                type="text"
                id="rss-url"
                className="input-field"
                value={rssUrl}
                onChange={(e) => setRssUrl(e.target.value)}
                placeholder="e.g., http://feeds.bbci.co.uk/news/rss.xml"
                required
              />
            </div>

            <div className="input-group">
              <label htmlFor="num-articles" className="label">Number of Articles:</label>
              <input
                type="number"
                id="num-articles"
                className="input-field"
                value={numArticles}
                onChange={(e) => setNumArticles(Math.max(1, parseInt(e.target.value) || 1))}
                min="1"
                max="10"
              />
            </div>

            <button type="submit" className="submit-button" disabled={loading}>
              {loading ? (
                <span className="loading-spinner-container">
                  <svg className="loading-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Summarizing RSS...
                </span>
              ) : (
                'Get RSS Summaries'
              )}
            </button>
          </form>
        </div>

        {/* Single Article Summarization Section */}
        <div className="summarization-section">
          <h2 className="section-heading">Summarize Single Article</h2>
          <form onSubmit={handleSummarizeArticle} className="form-section">
            <div className="input-group">
              <label htmlFor="article-url" className="label">Article URL:</label>
              <input
                type="text"
                id="article-url"
                className="input-field"
                value={articleUrl}
                onChange={(e) => setArticleUrl(e.target.value)}
                placeholder="e.g., https://www.nytimes.com/..."
                required
              />
            </div>

            <button type="submit" className="submit-button" disabled={loading}>
              {loading ? (
                <span className="loading-spinner-container">
                  <svg className="loading-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Summarizing Article...
                </span>
              ) : (
                'Get Article Summary'
              )}
            </button>
          </form>
        </div>

        {error && (
          <div className="error-message" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        {message && !error && (
          <div className="info-message">
            {message}
          </div>
        )}

        {summaries.length > 0 && (
          <div className="summaries-section">
            <h2 className="summaries-heading">Summaries:</h2>
            {summaries.map((article, index) => (
              <div key={index} className="article-summary-card">
                <h3 className="article-title">
                  <a href={article.link} target="_blank" rel="noopener noreferrer">
                    {article.title}
                  </a>
                </h3>
                <p className="article-summary">{article.summary}</p>
                <a href={article.link} target="_blank" rel="noopener noreferrer" className="article-link">Read Full Article</a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
