# Test script for Docker bot with new matches functionality

Write-Host "Testing Docker Bot with New Matches Functionality" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "Docker is running" -ForegroundColor Green
} catch {
    Write-Host "Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Check if docker-compose is available
try {
    docker-compose --version | Out-Null
    Write-Host "docker-compose is available" -ForegroundColor Green
} catch {
    Write-Host "docker-compose is not installed. Please install docker-compose first." -ForegroundColor Red
    exit 1
}

# Create .env file if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Please update .env with your actual values before running the bot" -ForegroundColor Yellow
}

# Build and start the bot
Write-Host "Building and starting the bot..." -ForegroundColor Blue
docker-compose -f docker-compose.bot.yml up --build -d

# Wait for services to be ready
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check if services are running
Write-Host "Checking service status..." -ForegroundColor Blue
docker-compose -f docker-compose.bot.yml ps

# Test the bot functionality
Write-Host "Testing bot functionality..." -ForegroundColor Blue
docker-compose -f docker-compose.bot.yml exec bot python scripts/test_bot_imports.py

# Show logs
Write-Host "Recent bot logs:" -ForegroundColor Blue
docker-compose -f docker-compose.bot.yml logs --tail=20 bot

Write-Host ""
Write-Host "Docker bot setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To interact with the bot:" -ForegroundColor Cyan
Write-Host "   1. Find your bot in Telegram" -ForegroundColor White
Write-Host "   2. Send /start command" -ForegroundColor White
Write-Host "   3. Click 'Matches' to test the new functionality" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "   - View logs: docker-compose -f docker-compose.bot.yml logs -f bot" -ForegroundColor White
Write-Host "   - Stop bot: docker-compose -f docker-compose.bot.yml down" -ForegroundColor White
Write-Host "   - Restart bot: docker-compose -f docker-compose.bot.yml restart bot" -ForegroundColor White
