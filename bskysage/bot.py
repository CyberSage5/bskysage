import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client, models
from loguru import logger
from ratelimit import limits, sleep_and_retry
from pydantic import BaseModel
import httpx
from playwright.sync_api import sync_playwright
import tempfile
from PIL import Image
import re

# Load environment variables
load_dotenv()

class Mention(BaseModel):
    uri: str
    cid: str
    text: str
    author: str
    parent_uri: Optional[str] = None
    parent_cid: Optional[str] = None
    processed: bool = False
    processed_at: Optional[datetime] = None

class BskySage:
    def __init__(self):
        try:
            # Create a new client and authenticate
            self.client = Client()
            self.client.login(
                os.getenv('BSKY_USERNAME'),
                os.getenv('BSKY_PASSWORD')
            )
            
            # Test the authentication by making a simple API call
            self.client.app.bsky.actor.get_profile({'actor': os.getenv('BSKY_USERNAME')})
            
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            raise
            
        self.bot_handle = os.getenv('BSKY_USERNAME')
        
    @sleep_and_retry
    @limits(calls=50, period=60)  # Rate limit for Bluesky API
    def fetch_mentions(self):
        """Fetch mentions of the bot from Bluesky"""
        try:
            notifications = self.client.app.bsky.notification.list_notifications()
            mentions = []
            
            for notif in notifications.notifications:
                if (notif.reason == 'mention' and 
                    not notif.is_read and 
                    f"@{self.bot_handle}" in notif.record.text):
                    
                    # Get parent URI and CID safely
                    parent_uri = None
                    parent_cid = None
                    if hasattr(notif.record, 'reply') and notif.record.reply:
                        if hasattr(notif.record.reply, 'parent') and notif.record.reply.parent:
                            parent_uri = notif.record.reply.parent.uri
                            parent_cid = notif.record.reply.parent.cid
                    
                    mention = Mention(
                        uri=notif.uri,
                        cid=notif.cid,
                        text=notif.record.text,
                        author=notif.author.handle,
                        parent_uri=parent_uri,
                        parent_cid=parent_cid,
                    )
                    mentions.append(mention)
            
            return mentions
        except Exception as e:
            logger.error(f"Error fetching mentions: {e}")
            return []

    def take_screenshot(self, post_url: str) -> Optional[str]:
        """Take a screenshot of a Bluesky post"""
        try:
            with sync_playwright() as p:
                # Launch browser with specific arguments for better performance
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-extensions',
                        '--disable-background-networking',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-breakpad',
                        '--disable-component-extensions-with-background-pages',
                        '--disable-default-apps',
                        '--disable-hang-monitor',
                        '--disable-ipc-flooding-protection',
                        '--disable-popup-blocking',
                        '--disable-prompt-on-repost',
                        '--disable-renderer-backgrounding',
                        '--disable-sync',
                        '--force-color-profile=srgb',
                        '--metrics-recording-only',
                        '--no-first-run',
                        '--password-store=basic',
                        '--use-mock-keychain',
                        '--window-size=1200,800'
                    ]
                )
                
                # Create a new context with specific viewport
                context = browser.new_context(
                    viewport={'width': 1200, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    ignore_https_errors=True,
                    bypass_csp=True
                )
                
                # Create a new page
                page = context.new_page()
                
                # Set longer timeout and enable JavaScript
                page.set_default_timeout(60000)  # 60 seconds timeout
                
                # Navigate to the post with specific wait conditions
                logger.info(f"Navigating to {post_url}")
                page.goto(post_url, wait_until='domcontentloaded', timeout=60000)
                
                # Wait for the post content to load with a more specific selector
                logger.info("Waiting for post content to load")
                
                # Try multiple selectors for Bluesky posts
                selectors = [
                    'article[data-testid="post"]',
                    'article',
                    'div[data-testid="post"]',
                    'div[class*="post"]',
                    'div[class*="Post"]'
                ]
                
                post_element = None
                for selector in selectors:
                    try:
                        logger.info(f"Trying selector: {selector}")
                        post_element = page.wait_for_selector(selector, timeout=10000)
                        if post_element:
                            logger.info(f"Found post with selector: {selector}")
                            break
                    except Exception as e:
                        logger.warning(f"Selector {selector} not found: {e}")
                
                if not post_element:
                    logger.error("Could not find post element with any selector")
                    # Take a screenshot anyway to see what's on the page
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        screenshot_path = tmp.name
                        page.screenshot(path=screenshot_path, full_page=True)
                    return screenshot_path
                
                # Scroll to the post element to ensure it's in view
                post_element.scroll_into_view_if_needed()
                
                # Wait a bit for any animations to complete
                page.wait_for_timeout(1000)
                
                # Take screenshot with specific options
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    screenshot_path = tmp.name
                    
                    # Try to take a screenshot of just the post element first
                    try:
                        post_element.screenshot(path=screenshot_path, type='png')
                        logger.info("Successfully took screenshot of post element")
                    except Exception as e:
                        logger.warning(f"Failed to take element screenshot: {e}")
                        # Fall back to full page screenshot
                        page.screenshot(
                            path=screenshot_path,
                            full_page=True,
                            type='png',
                            quality=100
                        )
                        logger.info("Took full page screenshot as fallback")
                
                # Close browser and context
                context.close()
                browser.close()
                
                return screenshot_path
                
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            logger.exception("Full traceback:")
            return None

    @sleep_and_retry
    @limits(calls=50, period=60)
    def post_reply(self, text: str, parent_uri: str, parent_cid: str, image_path: Optional[str] = None):
        """Post a reply to a mention with optional image"""
        try:
            # Format datetime in RFC-3339 format
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            # Prepare the post record
            post_record = {
                'text': text,
                'reply': {
                    'root': {
                        'uri': parent_uri,
                        'cid': parent_cid
                    },
                    'parent': {
                        'uri': parent_uri,
                        'cid': parent_cid
                    }
                },
                'createdAt': current_time
            }
            
            # If we have an image, upload it first
            if image_path:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                # Upload the image
                upload = self.client.com.atproto.repo.upload_blob({
                    'repo': self.bot_handle,
                    'data': image_data,
                    'contentType': 'image/png'
                })
                
                # Add the image to the post
                post_record['embed'] = {
                    'images': [{
                        'alt': 'Screenshot of the post',
                        'image': upload.blob
                    }]
                }
            
            # Create the post
            self.client.com.atproto.repo.create_record({
                'repo': self.bot_handle,
                'collection': 'app.bsky.feed.post',
                'record': post_record
            })
            
            # Clean up the temporary file if it exists
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
                
            return True
        except Exception as e:
            logger.error(f"Error posting reply: {e}")
            return False

    def process_mention(self, mention: Mention):
        """Process a single mention"""
        try:
            # Check if this is a screenshot request
            if not any(keyword in mention.text.lower() for keyword in ['screenshot', 'screenshot this']):
                logger.info(f"Ignoring non-screenshot mention: {mention.uri}")
                return
            
            logger.info(f"Processing screenshot request for mention: {mention.uri}")
            
            # Get the post URL
            post_url = None
            if mention.parent_uri:
                # Convert at:// URI to web URL
                uri_parts = mention.parent_uri.split('/')
                logger.info(f"Parent URI parts: {uri_parts}")
                
                if len(uri_parts) >= 3:
                    did = uri_parts[2]
                    rkey = uri_parts[-1]
                    post_url = f"https://bsky.app/profile/{did}/post/{rkey}"
                    logger.info(f"Generated post URL: {post_url}")
                else:
                    logger.error(f"Invalid parent URI format: {mention.parent_uri}")
            else:
                logger.warning("No parent URI found in mention")
            
            if not post_url:
                logger.error("Could not generate post URL")
                self.post_reply(
                    "I couldn't find the post to screenshot. Please make sure you're replying to a post.",
                    mention.uri,
                    mention.cid
                )
                return
            
            # Take the screenshot
            logger.info(f"Taking screenshot of: {post_url}")
            screenshot_path = self.take_screenshot(post_url)
            
            if not screenshot_path:
                logger.error("Failed to take screenshot")
                self.post_reply(
                    "Sorry, I couldn't take a screenshot of the post at this time.",
                    mention.uri,
                    mention.cid
                )
                return
            
            logger.info(f"Screenshot taken successfully: {screenshot_path}")
            
            # Post the reply with the screenshot
            support_message = "\n\nSupport BskySage: https://buymeacoffee.com/terfajohn44"
            self.post_reply(
                f"Here's your screenshot!{support_message}",
                mention.uri,
                mention.cid,
                screenshot_path
            )
            
            logger.info(f"Successfully posted reply with screenshot for mention: {mention.uri}")
            
        except Exception as e:
            logger.error(f"Error processing mention: {e}")
            logger.exception("Full traceback:")
            self.post_reply(
                "Sorry, I encountered an error while processing your request.",
                mention.uri,
                mention.cid
            ) 