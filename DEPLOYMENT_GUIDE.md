# 🚀 CricAlgo Bot Deployment Guide

## Quick Deploy to Railway (Recommended)

### Step 1: Prepare Your Code
1. Push your code to GitHub
2. Make sure all environment variables are documented

### Step 2: Deploy to Railway
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your CricAlgo repository
5. Railway will automatically detect your Dockerfile

### Step 3: Add Services
1. **PostgreSQL Database:**
   - Click "New" → "Database" → "PostgreSQL"
   - Railway will provide connection string

2. **Redis Cache:**
   - Click "New" → "Database" → "Redis"
   - Railway will provide connection string

### Step 4: Configure Environment Variables
In Railway dashboard, go to your service → Variables tab:

```
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres.railway.internal:5432/railway

# Redis
REDIS_URL=redis://redis.railway.internal:6379/0
CELERY_BROKER_URL=redis://redis.railway.internal:6379/1
CELERY_RESULT_BACKEND=redis://redis.railway.internal:6379/2

# App Configuration
APP_ENV=production
DEBUG=false
SECRET_KEY=your-secret-key-here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token-here

# Optional: Sentry for error tracking
SENTRY_DSN=your-sentry-dsn-here
```

### Step 5: Deploy
1. Railway will automatically deploy when you push to GitHub
2. Check logs in Railway dashboard
3. Your bot will be available at the provided URL

## Alternative: Render Deployment

### Step 1: Prepare for Render
1. Create `render.yaml` in your repo root
2. Push to GitHub

### Step 2: Deploy to Render
1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Click "New" → "Web Service"
4. Connect your repository
5. Configure environment variables
6. Deploy!

## Environment Variables Required

### Required Variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather
- `SECRET_KEY`: Random secret for JWT tokens
- `APP_ENV`: Set to "production"

### Optional Variables:
- `SENTRY_DSN`: For error tracking
- `DEBUG`: Set to "false" in production

## Database Setup

### For Railway:
1. Railway automatically creates PostgreSQL
2. Run migrations: `alembic upgrade head`
3. Seed initial data if needed

### For Render:
1. Add PostgreSQL service
2. Run migrations manually or via deployment script

## Monitoring Your Bot

### Health Checks:
- Railway: Automatic health checks at `/api/v1/health`
- Render: Configure health check path

### Logs:
- Railway: View logs in dashboard
- Render: View logs in dashboard

### Bot Status:
- Check Telegram bot is responding
- Monitor database connections
- Check Redis connectivity

## Troubleshooting

### Common Issues:
1. **Bot not responding**: Check TELEGRAM_BOT_TOKEN
2. **Database errors**: Verify DATABASE_URL
3. **Redis errors**: Verify REDIS_URL
4. **Deployment fails**: Check logs for missing dependencies

### Debug Steps:
1. Check environment variables
2. Verify database connections
2. Test bot endpoints
3. Check logs for errors

## Cost Comparison

| Platform | Free Tier | Database | Redis | Best For |
|----------|-----------|----------|-------|----------|
| Railway | $5/month credit | ✅ | ✅ | Easiest setup |
| Render | 750 hours/month | ✅ | ❌ | Simple apps |
| Heroku | Paid only | ✅ | ✅ | Enterprise |

## 🎛️ **Admin Dashboard Access**

### **Dashboard URL**
After deployment, access your admin dashboard at:
```
https://your-app-name.railway.app/admin
```

### **Creating Your First Admin Account**

**Step 1: Set Environment Variables**
In Railway dashboard, add these variables:
```
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_EMAIL=admin@yourdomain.com
SEED_ADMIN_PASSWORD=your-secure-password
```

**Step 2: Create Admin Account**
1. Go to Railway dashboard → Your service → Deployments
2. Click on the latest deployment
3. Go to "Logs" tab
4. Run this command in the terminal:
```bash
python scripts/create_admin.py
```

**Step 3: Access Dashboard**
1. Go to `https://your-app-name.railway.app/admin`
2. Login with your admin credentials
3. Set up 2FA using the QR code provided

### **Admin Dashboard Features**

#### **📊 Main Sections:**
- **Login** - Secure admin authentication with 2FA
- **Matches** - Manage cricket matches and contests
- **Finance** - Handle deposits, withdrawals, and transactions
- **Users** - User management and wallet operations
- **Audit Logs** - Track all admin actions

#### **🔧 Key Admin Functions:**
- **Deposit Management** - Approve/reject user deposits
- **Withdrawal Processing** - Process user withdrawal requests
- **Contest Settlement** - Settle contests and distribute prizes
- **Match Management** - Add/edit cricket matches
- **User Management** - View and manage user accounts
- **Financial Reports** - View transaction history and analytics

### **Security Features:**
- **2FA Authentication** - Two-factor authentication required
- **JWT Tokens** - Secure session management
- **Audit Logging** - All actions are logged
- **Role-based Access** - Admin-only features

## Next Steps After Deployment

1. **Create admin account** - Use the script above
2. **Test your bot** - Send messages to verify it works
3. **Access admin dashboard** - Manage your platform
4. **Set up monitoring** - Use Sentry for error tracking
5. **Configure webhooks** - If using webhook mode instead of polling
6. **Set up backups** - For production data
7. **Scale up** - When you need more resources

## Support

- Railway: [docs.railway.app](https://docs.railway.app)
- Render: [render.com/docs](https://render.com/docs)
- Telegram Bot API: [core.telegram.org/bots/api](https://core.telegram.org/bots/api)
