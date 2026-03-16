"""
TREND FINDER — Discovers Trending Topics in India

Sources (ALL FREE):
1. Google Trends India (RSS feed)
2. Reddit India subreddits
3. YouTube India trending page
4. Gemini AI trend analysis (when other sources used)

Features:
- Combines multiple sources for accuracy
- Filters for Indian audience relevance
- Ranks topics by trend score
- Avoids recently used topics
- Detailed logging for GitHub Actions
"""

import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TrendFinder:
    """Finds trending topics from multiple free sources"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8,te;q=0.7'
        }
        
        # Track used topics to avoid repeats
        self.history_file = "output/logs/topic_history.json"
        self.used_topics = self._load_history()
    

    def _load_history(self):
        """Load previously used topics"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    

    def _save_history(self, topic):
        """Save topic to history"""
        self.used_topics.append({
            'topic': topic,
            'used_at': datetime.now().isoformat()
        })
        
        # Keep only last 100 topics
        self.used_topics = self.used_topics[-100:]
        
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.used_topics, f, indent=2)
    

    def _is_topic_used(self, topic):
        """Check if topic was recently used"""
        topic_lower = topic.lower()
        for entry in self.used_topics[-30:]:  # Check last 30
            if topic_lower in entry.get('topic', '').lower():
                return True
        return False


    # =============================================
    # SOURCE 1: Google Trends India
    # =============================================
    
    def get_google_trends(self):
        """Scrape Google Trends trending searches for India"""
        
        logger.info("  📊 Fetching Google Trends India...")
        trending = []
        
        try:
            url = "https://trends.google.com/trending/rss?geo=IN"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')
                
                for item in items[:20]:
                    title = item.find('title')
                    traffic = item.find('ht:approx_traffic')
                    news_items = item.find_all('ht:news_item')
                    
                    if title:
                        # Parse traffic number
                        traffic_str = traffic.text.strip() if traffic else '0'
                        traffic_num = int(
                            traffic_str.replace('+', '').replace(',', '')
                        ) if traffic_str.replace('+', '').replace(',', '').isdigit() else 0
                        
                        # Get related news snippet
                        news_snippet = ''
                        if news_items:
                            news_title = news_items[0].find('ht:news_item_title')
                            if news_title:
                                news_snippet = news_title.text.strip()
                        
                        trending.append({
                            'topic': title.text.strip(),
                            'source': 'google_trends',
                            'traffic': traffic_num,
                            'news_snippet': news_snippet,
                            'score': traffic_num,
                            'timestamp': datetime.now().isoformat()
                        })
                
                logger.info(f"  ✅ Google Trends: Found {len(trending)} topics")
            else:
                logger.warning(f"  ⚠️ Google Trends: HTTP {response.status_code}")
                
        except Exception as e:
            logger.warning(f"  ⚠️ Google Trends failed: {e}")
        
        return trending


    # =============================================
    # SOURCE 2: Reddit India
    # =============================================
    
    def get_reddit_trends(self, niches=None):
        """Get trending topics from Indian subreddits"""
        
        logger.info("  📊 Fetching Reddit India trends...")
        
        subreddit_map = {
            'technology and AI': ['technology', 'artificial', 'MachineLearning', 'IndianGaming'],
            'space and science': ['space', 'science', 'Astronomy', 'Physics'],
            'amazing facts': ['todayilearned', 'interestingasfuck', 'Damnthatsinteresting'],
            'Indian history and mythology': ['india', 'IndiaSpeaks', 'indianhistory'],
            'personal finance India': ['IndiaInvestments', 'IndianStreetBets'],
            'health and fitness': ['HealthyFood', 'fitness', 'science'],
            'government schemes': ['india', 'IndiaSpeaks'],
        }
        
        # Flatten subreddits based on niches
        subreddits = set()
        if niches:
            for niche in niches:
                subs = subreddit_map.get(niche, [])
                subreddits.update(subs)
        else:
            for subs in subreddit_map.values():
                subreddits.update(subs)
        
        trending = []
        
        for sub in list(subreddits)[:10]:  # Max 10 subreddits
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10&t=day"
                response = requests.get(
                    url,
                    headers={
                        **self.headers,
                        'Accept': 'application/json'
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])
                    
                    for post in posts:
                        post_data = post.get('data', {})
                        score = post_data.get('score', 0)
                        
                        # Only high-scoring posts
                        if score > 100:
                            trending.append({
                                'topic': post_data.get('title', ''),
                                'source': f'reddit_r/{sub}',
                                'score': score,
                                'comments': post_data.get('num_comments', 0),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'timestamp': datetime.now().isoformat()
                            })
                
                # Respect rate limits
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"  ⚠️ Reddit r/{sub} failed: {e}")
                continue
        
        # Sort by engagement (score + comments)
        trending.sort(
            key=lambda x: x.get('score', 0) + x.get('comments', 0) * 2,
            reverse=True
        )
        
        logger.info(f"  ✅ Reddit: Found {len(trending)} topics")
        return trending[:15]


    # =============================================
    # SOURCE 3: YouTube Trending India
    # =============================================
    
    def get_youtube_trends(self):
        """Scrape YouTube trending page for India"""
        
        logger.info("  📊 Fetching YouTube India trends...")
        trending = []
        
        try:
            # YouTube trending API endpoint (no key needed for basic info)
            url = "https://www.youtube.com/feed/trending?gl=IN&hl=en"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                # Extract video titles from the page JSON data
                # YouTube embeds initial data as JSON in the page
                json_match = re.search(
                    r'var ytInitialData = ({.*?});',
                    response.text
                )
                
                if json_match:
                    try:
                        yt_data = json.loads(json_match.group(1))
                        
                        # Navigate YouTube's nested JSON structure
                        tabs = (yt_data.get('contents', {})
                               .get('twoColumnBrowseResultsRenderer', {})
                               .get('tabs', []))
                        
                        for tab in tabs:
                            content = (tab.get('tabRenderer', {})
                                      .get('content', {})
                                      .get('sectionListRenderer', {})
                                      .get('contents', []))
                            
                            for section in content:
                                items = (section.get('itemSectionRenderer', {})
                                        .get('contents', []))
                                
                                for item in items:
                                    shelf = item.get('shelfRenderer', {})
                                    shelf_content = (shelf.get('content', {})
                                                    .get('expandedShelfContentsRenderer', {})
                                                    .get('items', []))
                                    
                                    for video_item in shelf_content:
                                        video = video_item.get('videoRenderer', {})
                                        title_runs = video.get('title', {}).get('runs', [])
                                        
                                        if title_runs:
                                            trending.append({
                                                'topic': title_runs[0].get('text', ''),
                                                'source': 'youtube_trending',
                                                'video_id': video.get('videoId', ''),
                                                'views': video.get('viewCountText', {}).get('simpleText', ''),
                                                'score': 500,  # Base score for trending
                                                'timestamp': datetime.now().isoformat()
                                            })
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: regex extraction
                if not trending:
                    titles = re.findall(
                        r'"title":\{"runs":\[\{"text":"(.+?)"\}\]',
                        response.text
                    )
                    for title in titles[:20]:
                        trending.append({
                            'topic': title,
                            'source': 'youtube_trending',
                            'score': 300,
                            'timestamp': datetime.now().isoformat()
                        })
            
            logger.info(f"  ✅ YouTube Trending: Found {len(trending)} topics")
            
        except Exception as e:
            logger.warning(f"  ⚠️ YouTube trending failed: {e}")
        
        return trending[:15]


    # =============================================
    # COMBINED TREND ANALYSIS
    # =============================================
    
    def get_all_trends(self, niches=None):
        """
        Combine all trend sources and rank topics.
        
        Returns list of trending topics sorted by relevance score.
        """
        
        logger.info("📊 STEP: Gathering trending topics from all sources...")
        
        all_trends = []
        source_stats = {}
        
        # Collect from all sources
        google_trends = self.get_google_trends()
        all_trends.extend(google_trends)
        source_stats['Google Trends'] = len(google_trends)
        
        reddit_trends = self.get_reddit_trends(niches)
        all_trends.extend(reddit_trends)
        source_stats['Reddit'] = len(reddit_trends)
        
        youtube_trends = self.get_youtube_trends()
        all_trends.extend(youtube_trends)
        source_stats['YouTube'] = len(youtube_trends)
        
        # Log source statistics
        total = len(all_trends)
        logger.info(f"  📈 Trend sources summary:")
        for source, count in source_stats.items():
            logger.info(f"     {source}: {count} topics")
        logger.info(f"     Total: {total} topics")
        
        # Remove duplicates (similar topics)
        unique_trends = self._deduplicate(all_trends)
        logger.info(f"  🔄 After deduplication: {len(unique_trends)} unique topics")
        
        # Filter out used topics
        fresh_trends = [
            t for t in unique_trends 
            if not self._is_topic_used(t['topic'])
        ]
        logger.info(f"  🆕 After removing used topics: {len(fresh_trends)} fresh topics")
        
        # Sort by score
        fresh_trends.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Log top trends
        logger.info(f"  🏆 Top 5 trending topics:")
        for i, t in enumerate(fresh_trends[:5]):
            logger.info(f"     {i+1}. [{t['source']}] {t['topic'][:60]}...")
        
        return fresh_trends


    def _deduplicate(self, trends):
        """Remove duplicate/similar topics"""
        
        unique = []
        seen_keywords = set()
        
        for trend in trends:
            # Create a simplified key from topic
            key_words = set(
                re.sub(r'[^\w\s]', '', trend['topic'].lower()).split()
            )
            
            # Remove common words
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 
                         'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
            key_words -= stop_words
            
            # Check if significantly overlapping with any seen topic
            key_frozen = frozenset(key_words)
            
            is_duplicate = False
            for seen in seen_keywords:
                overlap = len(key_frozen & seen) / max(len(key_frozen | seen), 1)
                if overlap > 0.6:  # More than 60% overlap
                    is_duplicate = True
                    break
            
            if not is_duplicate and key_words:
                unique.append(trend)
                seen_keywords.add(key_frozen)
        
        return unique


    def mark_topic_used(self, topic):
        """Mark a topic as used (call after successful video creation)"""
        self._save_history(topic)
        logger.info(f"  📝 Topic marked as used: {topic[:50]}...")


# =============================================
# QUICK TEST
# =============================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(message)s'
    )
    
    finder = TrendFinder()
    
    # Test all sources
    trends = finder.get_all_trends(
        niches=['technology and AI', 'space and science']
    )
    
    print(f"\n{'='*60}")
    print(f"TOP TRENDING TOPICS")
    print(f"{'='*60}")
    
    for i, t in enumerate(trends[:10]):
        print(f"\n{i+1}. {t['topic']}")
        print(f"   Source: {t['source']} | Score: {t.get('score', 'N/A')}")
