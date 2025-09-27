#!/bin/bash

# Test script for Docker bot with new matches functionality

echo "🚀 Testing Docker Bot with New Matches Functionality"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

echo "✅ Docker and docker-compose are available"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your actual values before running the bot"
fi

# Build and start the bot
echo "🔨 Building and starting the bot..."
docker-compose -f docker-compose.bot.yml up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
docker-compose -f docker-compose.bot.yml ps

# Test the bot functionality
echo "🧪 Testing bot functionality..."
docker-compose -f docker-compose.bot.yml exec bot python scripts/test_bot_matches.py

# Show logs
echo "📋 Recent bot logs:"
docker-compose -f docker-compose.bot.yml logs --tail=20 bot

echo ""
echo "✅ Docker bot setup complete!"
echo ""
echo "📝 To interact with the bot:"
echo "   1. Find your bot in Telegram"
echo "   2. Send /start command"
echo "   3. Click '🏏 Matches' to test the new functionality"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: docker-compose -f docker-compose.bot.yml logs -f bot"
echo "   - Stop bot: docker-compose -f docker-compose.bot.yml down"
echo "   - Restart bot: docker-compose -f docker-compose.bot.yml restart bot"
