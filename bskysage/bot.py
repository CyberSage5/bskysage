import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client, models
from loguru import logger
from ratelimit import limits, sleep_and_retry
from openai import OpenAI
from pydantic import BaseModel
import httpx

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
            
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENROUTER_API_KEY'),
        )
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

    @sleep_and_retry
    @limits(calls=20, period=60)  # Rate limit for OpenRouter API
    def get_llm_response(self, context: str, question: str) -> str:
        """Get response from OpenRouter LLM"""
        try:
            logger.info(f"Sending request to OpenRouter API with context: {context[:100]}... and question: {question[:100]}...")
            
            response = self.openai_client.chat.completions.create(
                model="google/gemini-pro",
                messages=[
                    {"role": "system", "content": "You are BskySage, a helpful AI assistant on Bluesky. Provide accurate, concise, and focused responses. Stay on topic and answer only what was asked. Keep responses brief and to the point. If fact-checking, be objective and cite sources when possible. IMPORTANT: Keep each part under 280 characters."},
                    {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}\n\nPlease provide a focused, concise response that directly answers the question. If the response needs to be split, use [PART 1] and [PART 2] only. Each part must be under 280 characters."}
                ],
                max_tokens=150,  # Reduced to ensure brevity
                temperature=0.7,
            )
            
            logger.debug(f"OpenRouter API Response: {response}")
            
            if not response:
                logger.error("OpenRouter API returned empty response")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
                
            if not hasattr(response, 'choices'):
                logger.error(f"OpenRouter API response missing 'choices' attribute: {response}")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
                
            if not response.choices:
                logger.error("OpenRouter API response has empty choices")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
                
            if not hasattr(response.choices[0], 'message'):
                logger.error(f"OpenRouter API response choice missing 'message' attribute: {response.choices[0]}")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
                
            if not hasattr(response.choices[0].message, 'content'):
                logger.error(f"OpenRouter API response message missing 'content' attribute: {response.choices[0].message}")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
            
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                logger.error("OpenRouter API returned empty content")
                return ["I apologize, but I'm having trouble generating a response at the moment."]
            
            # Add Buy Me a Coffee link
            support_message = "\n\nSupport BskySage: https://buymeacoffee.com/terfajohn44"
            
            # Split content into parts if needed
            parts = []
            
            # Split by [PART X] markers or by length
            if "[PART" in content:
                parts = content.split("[PART")
                parts = [p.strip() for p in parts if p.strip()]
                # Limit to maximum 2 parts
                if len(parts) > 2:
                    parts = parts[:2]
            else:
                # If content is longer than 280 chars, split into 2 parts
                if len(content) > 280:
                    # Find the middle point at a space
                    mid_point = content[:280].rfind(" ")
                    if mid_point == -1:
                        mid_point = 280
                    parts = [content[:mid_point], content[mid_point:].strip()]
                else:
                    parts = [content]
            
            # Ensure each part is under 280 characters
            for i in range(len(parts)):
                if len(parts[i]) > 280:
                    parts[i] = parts[i][:277] + "..."
            
            # Add support message to the last part
            if parts:
                # Make sure the last part has room for the support message
                if len(parts[-1]) + len(support_message) > 280:
                    # If it doesn't fit, create a new part
                    if len(parts) < 2:
                        parts.append(support_message)
                    else:
                        # If we already have 2 parts, add to the last one and truncate
                        parts[-1] = parts[-1][:280-len(support_message)] + support_message
                else:
                    parts[-1] = parts[-1] + support_message
            
            logger.info(f"Split response into {len(parts)} parts")
            return parts
            
        except Exception as e:
            logger.error(f"Error getting LLM response: {str(e)}")
            logger.exception("Full traceback:")
            return ["I apologize, but I'm having trouble processing your request at the moment." + support_message]

    @sleep_and_retry
    @limits(calls=50, period=60)
    def post_reply(self, text: str, parent_uri: str, parent_cid: str, is_thread: bool = False):
        """Post a reply to a mention"""
        try:
            # Format datetime in RFC-3339 format
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            self.client.com.atproto.repo.create_record({
                'repo': self.bot_handle,
                'collection': 'app.bsky.feed.post',
                'record': {
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
            })
            return True
        except Exception as e:
            logger.error(f"Error posting reply: {e}")
            return False

    def process_mention(self, mention: Mention):
        """Process a single mention"""
        try:
            # Get parent post content if it exists
            context = ""
            if mention.parent_uri:
                try:
                    # Extract the DID from the parent URI
                    # Format: at://did:plc:xxx/app.bsky.feed.post/yyy
                    uri_parts = mention.parent_uri.split('/')
                    
                    # Handle different URI formats
                    if len(uri_parts) >= 3:
                        # Extract the DID part
                        repo_did = uri_parts[2]
                        
                        # Extract the post ID (rkey)
                        rkey = uri_parts[-1]
                        
                        logger.info(f"Fetching parent post with repo: {repo_did}, rkey: {rkey}")
                        
                        try:
                            parent_post = self.client.com.atproto.repo.get_record({
                                'repo': repo_did,
                                'collection': 'app.bsky.feed.post',
                                'rkey': rkey
                            })
                            
                            if parent_post and hasattr(parent_post, 'value') and hasattr(parent_post.value, 'text'):
                                context = parent_post.value.text
                                logger.info(f"Found parent post context: {context[:100]}...")
                            else:
                                logger.error(f"Parent post missing text: {parent_post}")
                        except Exception as e:
                            logger.error(f"Error fetching parent post record: {e}")
                            # Try alternative method if the first one fails
                            try:
                                # Try using the handle instead of DID
                                handle = mention.author.split('.')[0]
                                logger.info(f"Trying alternative method with handle: {handle}")
                                
                                parent_post = self.client.com.atproto.repo.get_record({
                                    'repo': handle,
                                    'collection': 'app.bsky.feed.post',
                                    'rkey': rkey
                                })
                                
                                if parent_post and hasattr(parent_post, 'value') and hasattr(parent_post.value, 'text'):
                                    context = parent_post.value.text
                                    logger.info(f"Found parent post context using handle: {context[:100]}...")
                                else:
                                    logger.error(f"Parent post missing text using handle: {parent_post}")
                            except Exception as e2:
                                logger.error(f"Error fetching parent post with handle: {e2}")
                    else:
                        logger.error(f"Invalid parent URI format: {mention.parent_uri}")
                except Exception as e:
                    logger.error(f"Error fetching parent post: {e}")
                    context = ""

            # Generate response
            response_parts = self.get_llm_response(context, mention.text)
            
            # Post replies
            last_uri = mention.uri
            last_cid = mention.cid
            
            for i, part in enumerate(response_parts):
                is_thread = i > 0
                if self.post_reply(part, last_uri, last_cid, is_thread):
                    mention.processed = True
                    mention.processed_at = datetime.utcnow()
                    logger.info(f"Successfully posted part {i+1} of response")
                else:
                    logger.error(f"Failed to post part {i+1} of response")
                    break
                
        except Exception as e:
            logger.error(f"Error processing mention {mention.uri}: {e}") 