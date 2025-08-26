import sys
import os

print("=== DEPLOYMENT TEST ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print("Environment variables check:")

# Check critical env vars
env_vars = ["OPENAI_API_KEY", "TWITTER_API_KEY", "TWITTER_API_SECRET", 
           "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]

for var in env_vars:
    value = os.getenv(var)
    print(f"{var}: {'SET' if value else 'MISSING'}")

print("\nTesting imports...")
try:
    import tweepy
    print("✓ tweepy imported")
except Exception as e:
    print(f"✗ tweepy failed: {e}")

try:
    from openai import OpenAI
    print("✓ openai imported")
except Exception as e:
    print(f"✗ openai failed: {e}")

try:
    import feedparser
    print("✓ feedparser imported")
except Exception as e:
    print(f"✗ feedparser failed: {e}")

print("\nTesting Twitter API...")
try:
    auth = tweepy.OAuth1UserHandler(
        os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET"),
        os.getenv("TWITTER_ACCESS_TOKEN"), os.getenv("TWITTER_ACCESS_SECRET")
    )
    twitter_client = tweepy.Client(
        consumer_key=os.getenv("TWITTER_API_KEY"),
        consumer_secret=os.getenv("TWITTER_API_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
    )
    me = twitter_client.get_me()
    print(f"✓ Twitter API works. User: {me.data.username}")
except Exception as e:
    print(f"✗ Twitter API failed: {e}")

print("=== TEST COMPLETE ===")