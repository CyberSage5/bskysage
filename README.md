# BskySage

BskySage is an AI-powered bot for Bluesky that provides intelligent responses to mentions and helps with fact-checking. Built with OpenRouter LLM integration, it's designed to handle high volumes of interactions while maintaining rate limits and ensuring reliable performance.

## Features

- Responds to mentions with AI-powered insights
- Fact-checks content when requested
- Handles both direct mentions and replies
- Rate-limited to prevent API exhaustion
- Queue-based processing for scalability
- Persistent tracking of processed mentions
- Threaded responses for longer content
- Buy Me a Coffee integration for support

## Prerequisites

- Python 3.8+
- Redis server
- Bluesky account
- OpenRouter API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bskysage.git
cd bskysage
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Create a `.env` file with the following variables:
```
BSKY_USERNAME=your_bot_handle
BSKY_PASSWORD=your_password
OPENROUTER_API_KEY=your_api_key
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # Optional
```

## Running the Bot

1. Start Redis server:
```bash
redis-server
```

2. Start the worker (in a separate terminal):
```bash
bskysage-worker
```

3. Start the main service (in another terminal):
```bash
bskysage-service
```

## Deployment on Render

### Prerequisites

1. A Render account
2. A Redis instance (you can use Render's Redis service)
3. Your Bluesky and OpenRouter credentials

### Deployment Steps

1. **Create a Redis Instance on Render**
   - Go to the Render dashboard
   - Click "New" and select "Redis"
   - Choose a name and plan
   - Note the Redis connection details

2. **Create a Web Service for the Worker**
   - Go to the Render dashboard
   - Click "New" and select "Web Service"
   - Connect your GitHub repository
   - Configure the service:
     - Name: `bskysage-worker`
     - Environment: `Python`
     - Build Command: `pip install -r requirements.txt && pip install -e .`
     - Start Command: `bskysage-worker`
     - Add the following environment variables:
       - `BSKY_USERNAME`
       - `BSKY_PASSWORD`
       - `OPENROUTER_API_KEY`
       - `REDIS_HOST` (from your Redis instance)
       - `REDIS_PORT` (from your Redis instance)
       - `REDIS_PASSWORD` (from your Redis instance)

3. **Create a Web Service for the Service**
   - Go to the Render dashboard
   - Click "New" and select "Web Service"
   - Connect your GitHub repository
   - Configure the service:
     - Name: `bskysage-service`
     - Environment: `Python`
     - Build Command: `pip install -r requirements.txt && pip install -e .`
     - Start Command: `bskysage-service`
     - Add the same environment variables as the worker

4. **Deploy Both Services**
   - Click "Create Web Service" for both services
   - Render will automatically deploy your services

## Usage

1. Mention the bot in a post or reply:
```
@bskysage.codafofo.dev Please fact-check this information
```

2. The bot will:
   - Process your mention
   - Analyze the context
   - Generate a response
   - Reply to your mention

## Rate Limits

- Bluesky API: 50 calls per minute
- OpenRouter API: 20 calls per minute
- Mention processing: Every 30 seconds

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'bskysage'**
   - Make sure you've installed the package in development mode: `pip install -e .`
   - Check that you're running the commands from the project root directory

2. **Redis Connection Error**
   - Ensure Redis server is running: `redis-server`
   - Check Redis connection settings in your .env file

3. **Bluesky Authentication Error**
   - Verify your Bluesky credentials in the .env file
   - Make sure your account has the necessary permissions

4. **OpenRouter API Error**
   - Check your OpenRouter API key in the .env file
   - Verify your API usage limits

### Logs

- Check the `bskysage.log` file for detailed error messages
- Logs are rotated when they reach 500 MB

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License 