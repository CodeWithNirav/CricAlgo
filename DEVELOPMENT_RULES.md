# Development Rules for CricAlgo

## Bot-Related Changes
**RULE**: Whenever you make changes to bot-related files, you MUST restart the bot container.

### Bot-Related Files:
- `app/bot/` (all files)
- `app/bot/handlers/` (all files)
- `app/bot/commands/` (all files)
- `app/bot/middleware/` (all files)
- Any file that affects bot functionality

### Restart Command:
```bash
docker restart cricalgo-bot-1
```

### Verification:
```bash
docker ps | findstr bot
```

## Contest Prize Structure
**RULE**: Default prize structure is ALWAYS 100% to 1st rank only.

### Implementation:
- Frontend: `[{"pos": 1, "pct": 100}]`
- Backend: `[{"pos": 1, "pct": 100}]`
- Database: JSON format with single winner

### Files to Update:
- `app/api/admin_matches_contests.py` - ContestCreate model
- `app/repos/contest_repo.py` - create_contest function
- `web/admin/src/pages/matches/MatchDetail.jsx` - Frontend form
- `app/core/config.py` - Documentation

## Database Changes
**RULE**: After making database schema changes, restart the application.

### Restart Command:
```bash
docker-compose restart app
```

## Testing Checklist
1. ✅ Check for linting errors
2. ✅ Restart affected containers
3. ✅ Test functionality
4. ✅ Verify database changes
5. ✅ Check logs for errors

## File Change Impact
- **Bot files** → Restart bot
- **API files** → Restart app (auto-reload)
- **Database files** → Restart app
- **Frontend files** → No restart needed (hot reload)
