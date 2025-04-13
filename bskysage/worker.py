import os
import redis
from rq import Worker, Queue, Connection
from loguru import logger
from .bot import BskySage, Mention

# Configure Redis connection
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', None),
    db=0
)

def process_mention(mention_data: dict):
    """Process a mention in the worker"""
    try:
        # Convert dict to Mention object
        mention = Mention(**mention_data)
        
        # Initialize bot
        bot = BskySage()
        
        # Process the mention
        bot.process_mention(mention)
        
        logger.info(f"Successfully processed mention {mention.uri}")
        
    except Exception as e:
        logger.error(f"Error processing mention in worker: {e}")
        logger.exception("Full traceback:")

def main():
    """Main entry point for the worker"""
    # Configure logging
    logger.add("bskysage.log", rotation="500 MB")
    
    # Start worker
    with Connection(redis_conn):
        worker = Worker([Queue('mentions')])
        worker.work()

if __name__ == '__main__':
    main() 