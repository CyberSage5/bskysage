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

# Initialize bot
bot = BskySage()

def process_mention(mention_data: dict):
    """Process a mention from the queue"""
    try:
        mention = Mention(**mention_data)
        bot.process_mention(mention)
    except Exception as e:
        logger.error(f"Error processing mention from queue: {e}")

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