"""
news_poster.py
Automates fetching news for EPL, F1, Cycling, Finance, Politics.
Generates witty GPT-powered hooks & posts to Twitter twice a day.
Enhanced version with better rate limiting, trend integration, URL validation, and content-aware posting.
"""

import os
import random
import requests
import feedparser
import tweepy
import schedule
import time
import hashlib
from datetime import datetime, timedelta
import pytz
from newspaper import Article
from openai import OpenAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import logging
from logging.handlers import RotatingFileHandler


# Load .env variables
load_dotenv()

# =========================
# CONFIGURATION
# =========================

# Load from environment variables (.env file in production)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Log files
LOG_FILE = "bot_log.txt"
POSTED_LOG = "posted_links.txt"
CONTENT_HASH_LOG = "posted_content_hashes.txt"

# Image folder
IMAGE_FOLDER = "images"

# Rate limiting configuration
DAILY_POST_LIMIT = 7
POST_INTERVAL_MINUTES = 120
last_post_time = None
FRESHNESS_WINDOW = timedelta(hours=24)


# RSS feeds mapped to categories

# RSS feeds mapped to categories
RSS_FEEDS = {
    "Arsenal": [
        "http://feeds.bbci.co.uk/sport/football/teams/arsenal/rss.xml",
        "https://www.theguardian.com/football/arsenal/rss",
        "https://www.skysports.com/rss/0,20514,11670,00.xml",
        "https://arseblog.com/feed/"
    ],
    "Manchester United": [
        "https://www.manutd.com/rss/news",
        "http://feeds.bbci.co.uk/sport/football/teams/manchester-united/rss.xml",
        "https://www.theguardian.com/football/manchester-united/rss",
        "https://www.skysports.com/rss/0,20514,11667,00.xml",
        "https://www.manchestereveningnews.co.uk/sport/football/manchester-united/rss.xml"
    ],
    "EPL": [
        "https://www.premierleague.com/rss",
        "http://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
        "https://www.theguardian.com/football/premierleague/rss",
        "https://www.skysports.com/rss/0,20514,11661,00.xml",
        "https://www.football.co.uk/rss/premier-league-news/"
    ],
    "F1": [
        "https://www.formula1.com/en/latest/all-news.rss",
        "https://www.autosport.com/rss/f1/news/",
        "https://www.motorsport.com/rss/f1/news/",
        "http://feeds.bbci.co.uk/sport/formula1/rss.xml"
    ],
    "MotoGP": [
        "https://www.motogp.com/en/rss",
        "https://www.motorsport.com/rss/motogp/news/",
        "https://www.autosport.com/rss/motogp/news/",
        "https://www.crash.net/rss/motogp",
        "https://www.the-race.com/rss/motogp/"
    ],
    "Kenyan Politics": [
        "https://www.standardmedia.co.ke/rss/politics.php",
        "https://nation.africa/kenya/rss/politics",
        "https://www.theeastafrican.co.ke/rss",
        "https://allafrica.com/tools/headlines/rss/kenya/headlines.rdf"
    ],
    "Kenyan Tourism": [
        "https://www.standardmedia.co.ke/rss/travel.php",
        "https://nation.africa/kenya/rss/lifestyle",
        "https://www.businessdailyafrica.com/rss.xml",
        "https://allafrica.com/tools/headlines/rss/tourism/headlines.rdf",
        "https://www.kbc.co.ke/feed/"
    ],
    "World Finance": [
        "https://www.reuters.com/arc/outboundfeeds/business/?outputType=xml",
        "https://www.ft.com/rss/home/uk",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.wsj.com/rss/",
        "https://feeds.bloomberg.com/markets/news.rss"
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://coinjournal.net/rss/",
        "https://crypto.news/feed/"
    ],
    "Cycling": [
        "https://www.cyclingnews.com/rss/",
        "https://www.bikeradar.com/feed/",
        "https://velo.outsideonline.com/feed/",
        "https://road.cc/rss"
    ],
    "Space Exploration": [
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "https://www.esa.int/rss",
        "https://www.space.com/feeds/all",
        "https://spacenews.com/feed/",
        "https://www.astronomy.com/rss-feeds/"
    ],
    "Tesla": [
        "https://electrek.co/feed/",
        "https://insideevs.com/rss/news/",
        "https://www.notateslaapp.com/feed",
        "https://ir.tesla.com/rss"
    ]
}

# Hashtag pools
CATEGORY_HASHTAGS = {
    "Arsenal": ["#Arsenal", "#COYG", "#PremierLeague", "#Saka", "#Odegaard", "#Saliba", "#Arteta", "#Gunners", "#AFC"],
    "Manchester United": ["#ManUtd", "#MUFC", "#PremierLeague", "#TenHag", "#Mainoo", "#Rashford", "#Hojlund", "#RedDevils"],
    "EPL": ["#PremierLeague", "#EPL", "#Football", "#ManCity", "#Liverpool", "#Chelsea", "#Arsenal", "#ManUtd", "#Spurs"],
    "F1": ["#F1", "#Formula1", "#Motorsport", "#Verstappen", "#Hamilton", "#Norris", "#Leclerc", "#McLaren", "#Ferrari", "#RedBull"],
    "MotoGP": ["#MotoGP", "#MotorcycleRacing", "#Bagnaia", "#Marquez", "#Quartararo", "#VR46", "#GrandPrix"],
    "Kenyan Politics": ["#Kenya", "#KenyaPolitics", "#Ruto", "#Gachagua", "#Raila", "#Azimio", "#UDA", "#AfricaPolitics"],
    "Kenyan Tourism": ["#MagicalKenya", "#KenyaTravel", "#Safari", "#Nairobi", "#Mombasa", "#KenyaTourism", "#VisitKenya"],
    "World Finance": ["#Finance", "#GlobalEconomy", "#Markets", "#Stocks", "#Investing", "#WallStreet", "#Bloomberg", "#Crypto"],
    "Crypto": ["#Cryptocurrency", "#Bitcoin", "#Ethereum", "#Blockchain", "#CryptoNews", "#DeFi", "#Web3", "#BTC"],
    "Cycling": ["#Cycling", "#TourDeFrance", "#ProCycling", "#Vingegaard", "#Pogacar", "#CyclistLife", "#RoadCycling"],
    "Space Exploration": ["#Space", "#NASA", "#SpaceX", "#Mars", "#MoonMission", "#Astronomy", "#Starlink", "#SpaceExploration"],
    "Tesla": ["#Tesla", "#ElonMusk", "#ElectricCars", "#ModelY", "#Cybertruck", "#TeslaNews", "#EV", "#SustainableTransport"]
}

# Mapping trends to categories
TREND_KEYWORDS = {
    "Arsenal": ["Arsenal", "Gunners", "Arteta", "Saka", "Odegaard", "Saliba", "Nwaneri", "Premier League"],
    "Manchester United": ["Manchester United", "Man Utd", "Ten Hag", "Mainoo", "Rashford", "Hojlund", "Red Devils", "Premier League"],
    "EPL": ["Premier League", "EPL", "Man City", "Liverpool", "Chelsea", "Arsenal", "Tottenham", "Football"],
    "F1": ["Formula 1", "F1", "Verstappen", "Norris", "Hamilton", "Leclerc", "McLaren", "Ferrari"],
    "MotoGP": ["MotoGP", "Bagnaia", "Marquez", "Quartararo", "Grand Prix", "Motorcycle Racing", "VR46"],
    "Kenyan Politics": ["Kenya", "Ruto", "Raila", "Gachagua", "UDA", "Azimio", "Nairobi", "Elections"],
    "Kenyan Tourism": ["Kenya", "Safari", "Nairobi", "Mombasa", "Magical Kenya", "Maasai Mara", "Tourism"],
    "World Finance": ["Finance", "Markets", "Economy", "Stocks", "Investing", "Wall Street", "Crypto", "Global Economy"],
    "Crypto": ["Cryptocurrency", "Bitcoin", "Ethereum", "Blockchain", "DeFi", "Web3", "NFTs", "BTC"],
    "Cycling": ["Cycling", "Tour de France", "Pogacar", "Vingegaard", "Vuelta", "Giro", "Road cycling"],
    "Space Exploration": ["Space", "NASA", "SpaceX", "Mars", "Moon Mission", "Starlink", "Astronomy"],
    "Tesla": ["Tesla", "Elon Musk", "Cybertruck", "Model Y", "Electric Vehicles", "EV", "Autonomous Driving"]
}

# Freshness + fallback
FALLBACK_KEYWORDS = {
    "Arsenal": ["Arsenal FC", "Gunners", "Premier League"],
    "Manchester United": ["Man Utd", "Red Devils", "Premier League"],
    "EPL": ["Premier League", "Football", "EPL"],
    "F1": ["Formula 1", "Grand Prix", "Motorsport"],
    "MotoGP": ["MotoGP", "Grand Prix", "Motorcycle Racing"],
    "Kenyan Politics": ["Kenya", "Nairobi", "Politics"],
    "Kenyan Tourism": ["Kenya", "Safari", "Tourism"],
    "World Finance": ["Finance", "Markets", "Economy"],
    "Crypto": ["Cryptocurrency", "Bitcoin", "Blockchain"],
    "Cycling": ["Cycling", "Tour de France", "Road Cycling"],
    "Space Exploration": ["Space", "NASA", "SpaceX"],
    "Tesla": ["Tesla", "Electric Vehicles", "Elon Musk"]
}

EVERGREEN_HOOKS = {
    "Arsenal": [
        "Arsenal fans know hope is the deadliest weapon. #COYG",
        "Every Arsenal season is a Shakespeare play: tragedy, comedy, miracle.",
        "Supporting Arsenal should come with free therapy sessions."
    ],
    "Manchester United": [
        "Man Utd: Where every match is a rollercoaster! #MUFC",
        "Red Devils never give up, even when the odds are grim.",
        "Supporting United is a lifestyle, not just a choice."
    ],
    "EPL": [
        "Premier League: Where dreams are made and hearts are broken.",
        "EPL weekends hit different. Who’s your team?",
        "Football’s home is the Premier League. #EPL"
    ],
    "F1": [
        "In F1, speed is everything—except when strategy is slower than dial-up.",
        "Formula 1: where even the safety car has a fanbase.",
        "Drivers chase glory, teams chase sponsors, fans chase sleep schedules."
    ],
    "MotoGP": [
        "MotoGP: Two wheels, one wild ride! 🏍️",
        "Speed, skill, and spills—MotoGP has it all.",
        "Who’s your pick for the next Grand Prix?"
    ],
    "Kenyan Politics": [
        "Kenya’s political scene: Never a dull moment! 🇰🇪",
        "From Nairobi to the nation, politics shapes Kenya’s future.",
        "Stay woke, Kenya’s political drama never sleeps."
    ],
    "Kenyan Tourism": [
        "Kenya: Where safaris meet stunning sunsets. 🌅",
        "Magical Kenya calls—ready for an adventure?",
        "From Maasai Mara to Mombasa, Kenya’s beauty shines."
    ],
    "World Finance": [
        "Markets move, money talks. What’s the next big trend? 📈",
        "Global finance: Where numbers tell epic stories.",
        "From Wall Street to Main Street, the economy never sleeps."
    ],
    "Crypto": [
        "Crypto: HODL or trade, what’s your vibe? ₿",
        "Bitcoin, Ethereum, or DeFi—pick your crypto adventure!",
        "Blockchain’s changing the game, one block at a time."
    ],
    "Cycling": [
        "Cycling: Two wheels, endless thrills. 🚴",
        "From Tour de France to local trails, pedal hard!",
        "Who’s ready to chase the peloton?"
    ],
    "Space Exploration": [
        "To the stars and beyond! 🚀 #SpaceExploration",
        "NASA, SpaceX, or ESA—who’s winning the space race?",
        "The universe is calling, and we’re listening."
    ],
    "Tesla": [
        "Tesla: Driving the future, one EV at a time. ⚡️",
        "Cybertruck or Model Y—pick your Tesla vibe!",
        "Elon’s vision keeps Tesla charging ahead."
    ]
}

# Image categories for better matching
IMAGE_CATEGORIES = {
    "Arsenal": ["arsenal", "football", "soccer", "gunners"],
    "Manchester United": ["manchester united", "manutd", "football", "red devils"],
    "EPL": ["football", "soccer", "premier", "epl"],
    "F1": ["f1", "racing", "formula", "motorsport"],
    "MotoGP": ["motogp", "motorcycle", "racing", "grand prix"],
    "Kenyan Politics": ["kenya", "politics", "nairobi", "africa"],
    "Kenyan Tourism": ["kenya", "safari", "tourism", "maasai mara"],
    "World Finance": ["finance", "money", "business", "stocks"],
    "Crypto": ["crypto", "bitcoin", "blockchain", "ethereum"],
    "Cycling": ["cycling", "bike", "tour", "bicycle"],
    "Space Exploration": ["space", "nasa", "spacex", "astronomy"],
    "Tesla": ["tesla", "electric car", "cybertruck", "elon musk"]
}


# GPT Client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Twitter Client
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
twitter_api = tweepy.API(auth)
twitter_client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)

def write_log(message, level="info"):
    """Append timestamped logs to bot_log.txt"""
    if level == "error":
        logging.error(message)
    else:
        logging.info(message)

# =========================
# UTILITY FUNCTIONS
# =========================

def validate_env_vars():
    """Validate required environment variables."""
    required_vars = ["OPENAI_API_KEY", "TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        write_log(f"Missing environment variables: {', '.join(missing)}", level="error")
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

def validate_url(url, timeout=8):
    """Validate that a URL is accessible and returns valid content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return True
        elif response.status_code in [301, 302, 307, 308]:
            write_log(f"URL redirected but accessible: {url}")
            return True
        elif response.status_code == 405:
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                return response.status_code == 200
            except:
                return False
        elif response.status_code == 403:
            write_log(f"URL blocked (403 Forbidden): {url}", level="error")
            return False
        else:
            write_log(f"URL validation failed - Status {response.status_code}: {url}")
            return False
    except requests.exceptions.ConnectionError:
        write_log(f"URL validation failed - Connection error: {url}")
        return False
    except requests.exceptions.Timeout:
        write_log(f"URL validation failed - Timeout: {url}")
        return False
    except requests.exceptions.TooManyRedirects:
        write_log(f"URL validation failed - Too many redirects: {url}")
        return False
    except Exception as e:
        write_log(f"URL validation failed - Unknown error: {url} ({e})")
        return False

def has_been_posted(url):
    """Check if a URL has already been posted."""
    if not os.path.exists(POSTED_LOG):
        return False
    with open(POSTED_LOG, "r") as f:
        return url.strip() in f.read()

def get_content_hash(title):
    """Generate hash for content similarity checking."""
    normalized = title.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()

def has_similar_content_posted(title):
    """Check if similar content has been posted recently."""
    if not os.path.exists(CONTENT_HASH_LOG):
        return False
    content_hash = get_content_hash(title)
    with open(CONTENT_HASH_LOG, "r") as f:
        return content_hash in f.read()

def log_content_hash(title):
    """Record content hash to prevent similar posts."""
    content_hash = get_content_hash(title)
    with open(CONTENT_HASH_LOG, "a") as f:
        f.write(f"{content_hash}\n")

def log_posted(url):
    """Record posted URL."""
    with open(POSTED_LOG, "a") as f:
        f.write(url.strip() + "\n")

def shorten_url(url):
    """Optional: Integrate Bitly or TinyURL for shortening."""
    return url

def validate_tweet_length(text):
    """Ensure tweet doesn't exceed Twitter's character limit."""
    if len(text) > 280:
        return text[:277] + "..."
    return text

def can_post_now():
    """Check if enough time has passed since last post."""
    global last_post_time
    if last_post_time is None:
        return True
    time_since_last = datetime.now(pytz.UTC) - last_post_time
    return time_since_last.total_seconds() >= (POST_INTERVAL_MINUTES * 60)


# =========================
# NEWS FETCHING
# =========================

def fetch_rss(feed_url):
    """Fetch news from an RSS feed with better error handling."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(feed_url, headers=headers, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.bozo:
            write_log(f"Feed parsing issues for {feed_url} - continuing anyway")
        articles = []
        for entry in feed.entries[:5]:
            article = {
                "title": entry.title,
                "url": entry.link,
                "published_parsed": getattr(entry, 'published_parsed', None)
            }
            articles.append(article)
        return articles
    except Exception as e:
        write_log(f"Error fetching RSS from {feed_url}: {e}")
        return []

def is_fresh(article):
    """Check if article is within freshness window."""
    pub_date = article.get('published_parsed')
    if not pub_date:
        return True
    try:
        dt = datetime(*pub_date[:6], tzinfo=pytz.UTC)
        return datetime.now(pytz.UTC) - dt <= FRESHNESS_WINDOW
    except:
        return True
        
def get_articles_for_category(category):
    """Get articles for a category by looping through all RSS feeds."""
    feeds = RSS_FEEDS.get(category, [])
    articles = []
    for feed in feeds:
        write_log(f"Processing RSS feed for {category}: {feed}")
        feed_articles = fetch_rss(feed)
        articles.extend(feed_articles)
    if not articles:
        write_log(f"No articles found for {category} after checking all feeds")
        if category in FALLBACK_KEYWORDS:
            write_log(f"Trying fallback keywords for {category}...")
            for alt in FALLBACK_KEYWORDS[category]:
                for feed in feeds:
                    feed_articles = fetch_rss(feed)
                    articles.extend(feed_articles)
                    if feed_articles:
                        write_log(f"Found {len(feed_articles)} articles with fallback keyword '{alt}' from {feed}")
    write_log(f"Total articles fetched for {category}: {len(articles)}")
    return articles


# =========================
# CONTENT-AWARE POST GENERATION
# =========================

def extract_article_content(url):
    """Fetch and extract main content from article URL using BeautifulSoup only."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to get meta description first
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'][:500]
        
        # Fallback to first substantial paragraph
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 50:
                return text[:500]
        
        return None
        
    except Exception as e:
        write_log(f"Could not extract content from {url}: {e}")
        return None

def generate_content_aware_post(title, category, article_url, trend_term=None):
    """Generate relevant post based on actual article content using GPT."""
    try:
        article_content = extract_article_content(article_url)
        content_context = f"Title: {title}\n"
        if article_content:
            content_context += f"Content: {article_content}\n"
        content_context += f"Category: {category}\n"
        if trend_term:
            content_context += f"Trending topic: {trend_term}\n"
        
        prompt = f"""Based on this news article, create an engaging Twitter post (under 200 characters to leave room for URL and hashtags):

{content_context}

Requirements:
- Be specific about the actual content/news
- Make it engaging and conversational
- Don't use generic templates
- Focus on the key newsworthy element
- Use appropriate tone for {category}
- Include relevant emojis if appropriate

Write ONLY the tweet text, no quotes or explanations:"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a witty social media manager creating engaging, specific tweets about current events."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        gpt_text = response.choices[0].message.content.strip()
        
        if trend_term and len(gpt_text) < 180:
            gpt_text = f"Trending {trend_term}: {gpt_text}"
        
        tags = CATEGORY_HASHTAGS.get(category, [])
        if tags:
            remaining_space = 240 - len(gpt_text)
            selected_tags = []
            for tag in tags[:3]:
                if tag.replace("#", "").lower() in gpt_text.lower() or tag.replace("#", "").lower() in title.lower():
                    if len(" " + tag) <= remaining_space and len(selected_tags) < 2:
                        selected_tags.append(tag)
                        remaining_space -= len(" " + tag)
            if selected_tags:
                gpt_text += " " + " ".join(selected_tags)
        
        return validate_tweet_length(gpt_text)
    
    except Exception as e:
        write_log(f"GPT generation failed: {e}")
        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a witty social media manager creating engaging, specific tweets about current events."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            gpt_text = response.choices[0].message.content.strip()
            return validate_tweet_length(gpt_text)
        except Exception as e2:
            write_log(f"Fallback GPT generation failed: {e2}")
            return generate_fallback_post(title, category, trend_term)

def generate_fallback_post(title, category, trend_term=None):
    """Simple fallback when GPT fails - still better than generic templates."""
    if ":" in title:
        main_part = title.split(":")[0].strip()
    else:
        main_part = title[:80]
    
    category_prefixes = {
        "Arsenal": ["Arsenal news:", "Gunners update:", "Arsenal:"],
        "Manchester United": ["Man Utd news:", "Red Devils update:", "MUFC:"],
        "EPL": ["Premier League:", "EPL update:"],
        "F1": ["F1 news:", "Formula 1:"],
        "MotoGP": ["MotoGP news:", "Grand Prix update:"],
        "Kenyan Politics": ["Kenya:", "Politics news:"],
        "Kenyan Tourism": ["Kenya travel:", "Safari update:"],
        "World Finance": ["Markets:", "Finance:"],
        "Crypto": ["Crypto news:", "Blockchain update:"],
        "Cycling": ["Cycling news:", "Pro cycling:"],
        "Space Exploration": ["Space news:", "NASA update:"],
        "Tesla": ["Tesla news:", "EV update:"]
    }
    
    prefix = random.choice(category_prefixes.get(category, ["News:"]))
    tweet_text = f"{prefix} {main_part}"
    
    if trend_term:
        tweet_text = f"Trending {trend_term} - {tweet_text}"
    
    tags = CATEGORY_HASHTAGS.get(category, [])
    if tags and len(tweet_text) < 200:
        tweet_text += " " + tags[0]
    
    return validate_tweet_length(tweet_text)

# =========================
# POST TO TWITTER
# =========================

def pick_relevant_image(category):
    """Modified for Railway - images won't persist"""
    write_log("Images not available in Railway environment")
    return None
    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if not files:
        write_log(f"No image files found in '{IMAGE_FOLDER}'")
        return None
    category_keywords = IMAGE_CATEGORIES.get(category, [])
    relevant_files = []
    for file in files:
        file_lower = file.lower()
        if any(keyword in file_lower for keyword in category_keywords):
            relevant_files.append(file)
    if not relevant_files:
        write_log(f"No images match keywords for category '{category}': {category_keywords}")
        chosen_files = files
    else:
        chosen_files = relevant_files
    chosen_image = os.path.join(IMAGE_FOLDER, random.choice(chosen_files))
    write_log(f"Selected image: {chosen_image}")
    return chosen_image

def post_tweet(text, category=None):
    """Post tweet with improved rate limiting and error handling."""
    global last_post_time
    if not can_post_now():
        write_log("Too soon to post. Waiting for rate limit window...")
        return False
    retries = 3
    for attempt in range(retries):
        try:
            text = validate_tweet_length(text)
            image_path = pick_relevant_image(category) if category else None
            media_ids = []
            if image_path and os.path.exists(image_path):
                media = twitter_api.media_upload(image_path)
                media_ids = [media.media_id]
            twitter_client.create_tweet(text=text, media_ids=media_ids or None)
            write_log(f"Tweet posted {'with image' if media_ids else 'without image'}")
            last_post_time = datetime.now(pytz.UTC)
            return True
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                wait_time = 15 * 60
                write_log(f"Rate limit hit. Waiting {wait_time/60} minutes before retry...")
                time.sleep(wait_time)
            elif "duplicate" in error_msg.lower():
                write_log("Duplicate tweet detected. Skipping...")
                return False
            else:
                write_log(f"Error posting tweet (attempt {attempt + 1}): {e}")
                if attempt == retries - 1:
                    return False
                time.sleep(30)
    return False
# =========================
# TREND DETECTION
# =========================

def detect_category_from_trends():
    """Fetch trending topics from Twitter and match to categories."""
    try:
        category_woeids = {
            "Kenyan Politics": 23424863,
            "Kenyan Tourism": 23424863,
            "Arsenal": 1,
            "Manchester United": 1,
            "EPL": 1,
            "F1": 1,
            "MotoGP": 1,
            "World Finance": 1,
            "Crypto": 1,
            "Cycling": 1,
            "Space Exploration": 1,
            "Tesla": 1
        }
        category = random.choice(list(RSS_FEEDS.keys()))
        woeid = category_woeids.get(category, 1)
        trends_result = twitter_api.get_place_trends(woeid)
        trends = [t["name"] for t in trends_result[0]["trends"]]
        write_log(f"Trending terms for WOEID {woeid}: {trends[:5]}")
        for trend in trends:
            for cat, keywords in TREND_KEYWORDS.items():
                if any(kw.lower() in trend.lower() for kw in keywords):
                    write_log(f"Trend '{trend}' matched to category '{cat}'")
                    return cat, trend
        write_log(f"No trend match found. Using fallback category: {category}")
        return category, None
    except Exception as e:
        write_log(f"Twitter trends error: {e}")
        return random.choice(list(RSS_FEEDS.keys())), None


# =========================
# NEWS + FALLBACK FLOW
# =========================

def get_articles_for_category(category):
    """Get articles for a category with fallback handling."""
    feeds = RSS_FEEDS.get(category, [])
    articles = []
    for feed in feeds:
        feed_articles = fetch_rss(feed)
        articles.extend(feed_articles)
        if articles:
            break
    if not articles and category in FALLBACK_KEYWORDS:
        write_log(f"No articles found for {category}, trying fallback keywords...")
        for alt in FALLBACK_KEYWORDS[category]:
            for feed in feeds:
                articles.extend(fetch_rss(feed))
            if articles:
                break
    return articles

def fallback_tweet(category):
    """Generate fallback tweet when no news is available."""
    if category in EVERGREEN_HOOKS:
        tweet = random.choice(EVERGREEN_HOOKS[category])
        tags = CATEGORY_HASHTAGS.get(category, [])
        if tags:
            additional_tags = random.sample(tags, min(2, len(tags)))
            tweet += " " + " ".join(additional_tags)
        return validate_tweet_length(tweet)
    return validate_tweet_length(f"No fresh news today for {category}, but the passion never stops!")

def post_dynamic_update(category, trend_term=None):
    """Post update for category with content-aware generation and URL validation."""
    articles = get_articles_for_category(category)
    fresh_articles = [a for a in articles if is_fresh(a)]
    target_articles = fresh_articles if fresh_articles else articles
    valid_articles_processed = 0
    for article in target_articles:
        if has_been_posted(article["url"]) or has_similar_content_posted(article["title"]):
            continue
        if not validate_url(article["url"]):
            write_log(f"Skipping article with broken URL: {article['title'][:60]}...")
            continue
        valid_articles_processed += 1
        post_text = generate_content_aware_post(
            article["title"], 
            category, 
            article["url"], 
            trend_term
        )
        tweet_text = f"{post_text}\n\n{article['url']}"
        if post_tweet(tweet_text, category):
            log_posted(article["url"])
            log_content_hash(article["title"])
            write_log(f"Posted content-aware article from {category}")
            return True
    if valid_articles_processed == 0:
        write_log(f"No valid URLs found for {category} articles")
    write_log(f"No new articles for {category}, posting evergreen content...")
    tweet = fallback_tweet(category)
    return post_tweet(tweet, category)

# =========================
# MAIN LOGIC
# =========================

def run_dynamic_job():
    """Runs a dynamic posting job with trend integration."""
    try:
        write_log("Starting dynamic job...")
        category, trend_term = detect_category_from_trends()
        success = post_dynamic_update(category, trend_term)
        if not success:
            write_log("Primary category failed, trying random category...")
            backup_categories = [cat for cat in RSS_FEEDS.keys() if cat != category]
            random.shuffle(backup_categories)
            for backup_category in backup_categories[:2]:
                if post_dynamic_update(backup_category):
                    break
        write_log("Dynamic job completed")
    except Exception as e:
        write_log(f"Error in run_dynamic_job: {e}")

# =========================
# SCHEDULER
# =========================

def schedule_posts():
    """Schedule posts with better timing."""
    times = ["05:30", "09:30", "12:00", "15:00", "17:30", "20:00", "22:30"]
    for t in times:
        schedule.every().day.at(t).do(run_dynamic_job)
        write_log(f"Dynamic job scheduled at {t}")
    schedule.every(POST_INTERVAL_MINUTES).minutes.do(run_dynamic_job).tag('interval-check')

def start_scheduler():
    """Start the scheduler with initial setup."""
    schedule_posts()
    write_log("Scheduler started with dynamic trending jobs.")
    write_log(f"Rate limiting: {DAILY_POST_LIMIT} posts/day, {POST_INTERVAL_MINUTES}min intervals")
    while True:
        schedule.run_pending()
        time.sleep(60)

# =========================
# TESTING & MANUAL FUNCTIONS
# =========================

def test_single_post(category=None):
    """Test function for single post."""
    if category is None:
        category, trend_term = detect_category_from_trends()
    else:
        trend_term = None
    write_log(f"Testing single post for category: {category}")
    post_dynamic_update(category, trend_term)

def test_url_validation(url):
    """Test function to check URL validation."""
    print(f"Testing URL: {url}")
    is_valid = validate_url(url)
    print(f"Result: {'Valid' if is_valid else 'Invalid'}")
    return is_valid

def test_full_pipeline(category="Arsenal"):
    """Test the complete pipeline including URL validation."""
    write_log(f"Testing full pipeline for {category}...")
    articles = get_articles_for_category(category)
    if not articles:
        write_log("No articles found")
        return
    for article in articles[:3]:
        print(f"\nTesting: {article['title']}")
        print(f"URL: {article['url']}")
        if validate_url(article['url']):
            print("URL: VALID")
            content = extract_article_content(article['url'])
            print(f"Content extracted: {'Yes' if content else 'No'}")
        else:
            print("URL: INVALID - would skip this article")
        print("-" * 50)

def test_content_extraction(url):
    """Test function to see content extraction in action."""
    content = extract_article_content(url)
    print(f"Extracted content: {content}")
    return content

#if __name__ == "__main__":
    #validate_env_vars()
    #test_single_post("EPL")
    # test_url_validation("https://www.autosport.com/f1/news/will-f1-get-too-complex-in-2026-fia-responds-to-driver-concerns/")
    # test_full_pipeline("Arsenal")
    #start_scheduler()
    
if __name__ == "__main__":
    try:
        validate_env_vars()
        start_scheduler()
    except Exception as e:
        write_log(f"Fatal error: {e}", level="error")
        time.sleep(60)  # Prevent rapid restarts
        raise

