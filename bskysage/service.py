import os
import time
import redis
from rq import Queue
from loguru import logger
from .bot import BskySage

class BskySageService:
    def __init__(self):
        self.redis_conn = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', None),
            db=0
        )
        self.queue = Queue('mentions', connection=self.redis_conn)
        self.bot = BskySage()
        
    def run(self):
        """Run the BskySage service"""
        logger.info("Starting BskySage screenshot service...")
        
        while True:
            try:
                # Fetch new mentions
                mentions = self.bot.fetch_mentions()
                
                # Add mentions to queue
                for mention in mentions:
                    if not self.redis_conn.sismember('processed_mentions', mention.uri):
                        self.queue.enqueue('bskysage.worker.process_mention', mention.dict())
                        self.redis_conn.sadd('processed_mentions', mention.uri)
                        logger.info(f"Added mention {mention.uri} to queue")
                
                # Sleep for a short interval
                time.sleep(30)  # Check for new mentions every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in BskySage service: {e}")
                time.sleep(60)  # Wait longer on error

def main():
    """Main entry point for the service"""
    # Configure logging
    logger.add("bskysage.log", rotation="500 MB")
    
    # Start service
    service = BskySageService()
    service.run()

if __name__ == '__main__':
    main() 