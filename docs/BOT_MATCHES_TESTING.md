# Bot Matches Functionality Testing Guide

## Overview

This guide explains how to test the new matches functionality in the CricAlgo bot. The bot has been updated to show matches instead of contests directly, providing a better user experience.

## New User Flow

1. **User clicks "🏏 Matches"** → Shows list of available matches (non-started)
2. **User clicks on a match** → Shows all contests for that specific match
3. **User can join contests** → Same contest joining flow as before

## Changes Made

### Files Modified
- `app/repos/match_repo.py` (new file)
- `app/bot/handlers/unified_callbacks.py`
- `app/bot/handlers/commands.py`
- `app/bot/handlers/callbacks.py`
- `app/bot/handlers/contest_callbacks.py`
- `app/bot/handlers/commands_clean.py`

### New Features
- **Match Repository**: Functions to get matches, get match by ID, and get contests for a specific match
- **Matches Handler**: Shows all available matches that haven't started yet
- **Match Contests Handler**: Shows contests for a specific match when user clicks on a match

## Testing the Docker Bot

### Prerequisites
- Docker and Docker Compose installed
- Telegram bot token configured
- Database and Redis services available

### Quick Test (Windows PowerShell)

```powershell
# Run the automated test script
.\scripts\test_docker_bot.ps1
```

### Manual Testing Steps

1. **Start the Docker bot:**
   ```bash
   make bot-docker
   # or
   docker-compose -f docker-compose.bot.yml up --build
   ```

2. **Check service status:**
   ```bash
   docker-compose -f docker-compose.bot.yml ps
   ```

3. **View bot logs:**
   ```bash
   docker-compose -f docker-compose.bot.yml logs -f bot
   ```

4. **Test in Telegram:**
   - Find your bot in Telegram
   - Send `/start` command
   - Click "🏏 Matches" button
   - Select a match to see its contests
   - Try joining a contest

### Environment Setup

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Update .env with your values:**
   ```env
   TELEGRAM_BOT_TOKEN=your-bot-token-here
   DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/cricalgo
   REDIS_URL=redis://redis:6379/0
   ```

### Testing Scripts

- `scripts/test_bot_imports.py` - Test that all imports work
- `scripts/test_bot_matches.py` - Test match functionality (requires database)
- `scripts/test_docker_bot.ps1` - Automated Docker test (Windows)
- `scripts/test_docker_bot.sh` - Automated Docker test (Linux/Mac)

### Useful Commands

```bash
# Start bot
make bot-docker

# View logs
docker-compose -f docker-compose.bot.yml logs -f bot

# Stop bot
docker-compose -f docker-compose.bot.yml down

# Restart bot
docker-compose -f docker-compose.bot.yml restart bot

# Shell into bot container
docker-compose -f docker-compose.bot.yml exec bot bash

# Test imports
python scripts/test_bot_imports.py
```

## Expected Behavior

### Before (Old Flow)
1. User clicks "🏏 Contests" → Shows all contests from all matches

### After (New Flow)
1. User clicks "🏏 Matches" → Shows list of matches
2. User clicks on a match → Shows contests for that match only
3. User can join contests as before

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Ensure PostgreSQL is running
   - Check DATABASE_URL in .env file
   - Verify database credentials

2. **Bot Not Responding**
   - Check bot token in .env file
   - Verify bot is running: `docker-compose -f docker-compose.bot.yml ps`
   - Check logs: `docker-compose -f docker-compose.bot.yml logs bot`

3. **Import Errors**
   - Run: `python scripts/test_bot_imports.py`
   - Check that all files are properly copied to Docker container

### Debug Commands

```bash
# Check container status
docker-compose -f docker-compose.bot.yml ps

# View all logs
docker-compose -f docker-compose.bot.yml logs

# Test imports inside container
docker-compose -f docker-compose.bot.yml exec bot python scripts/test_bot_imports.py

# Shell into container
docker-compose -f docker-compose.bot.yml exec bot bash
```

## Success Criteria

✅ **Bot starts without errors**
✅ **All imports work correctly**
✅ **Matches button appears in main menu**
✅ **Clicking Matches shows available matches**
✅ **Clicking a match shows its contests**
✅ **Contest joining works as before**

## Next Steps

After successful testing:
1. Deploy to staging environment
2. Test with real users
3. Monitor bot performance
4. Deploy to production

---

**Note**: This functionality requires matches to be created in the database. If no matches exist, the bot will show "No Matches Available" message.
