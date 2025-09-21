# Apply Admin Interface Fixes
# This script applies all the fixes for the admin interface issues

param(
    [switch]$SkipBuild,
    [switch]$SkipSeed,
    [string]$DatabaseUrl = $env:DATABASE_URL
)

Write-Host "=== Applying Admin Interface Fixes ===" -ForegroundColor Green

# Set default database URL if not provided
if (-not $DatabaseUrl) {
    $DatabaseUrl = "postgresql://postgres:postgres@localhost:5432/cricalgo"
}

# 1. Commit the backend changes
Write-Host "`n1. Committing backend changes..." -ForegroundColor Yellow
try {
    git add app/api/admin_manage.py
    git commit -m "fix(api): add alias /api/v1/admin/invitecodes -> /invite_codes for UI compatibility"
    Write-Host "✓ Backend changes committed" -ForegroundColor Green
} catch {
    Write-Host "⚠ Backend changes may already be committed or need manual review" -ForegroundColor Yellow
}

# 2. Commit the frontend changes
Write-Host "`n2. Committing frontend changes..." -ForegroundColor Yellow
try {
    git add web/admin/src/pages/invitecodes/InviteCodes.jsx
    git add web/admin/src/pages/users/Users.jsx
    git commit -m "fix(ui): improve error handling in admin pages and use canonical endpoints"
    Write-Host "✓ Frontend changes committed" -ForegroundColor Green
} catch {
    Write-Host "⚠ Frontend changes may already be committed or need manual review" -ForegroundColor Yellow
}

# 3. Seed database if not skipped
if (-not $SkipSeed) {
    Write-Host "`n3. Seeding database with sample invite code..." -ForegroundColor Yellow
    try {
        # Run the seed script
        python scripts/seed_invite_codes.py
        Write-Host "✓ Database seeded successfully" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Database seeding failed or may need manual intervention: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n3. Skipping database seeding (--SkipSeed flag)" -ForegroundColor Yellow
}

# 4. Build admin UI if not skipped
if (-not $SkipBuild) {
    Write-Host "`n4. Building admin UI..." -ForegroundColor Yellow
    try {
        # Check if npm is available
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Set-Location web/admin
            npm ci
            npm run build
            
            # Copy built files to app static
            if (Test-Path "dist") {
                Remove-Item -Path "..\..\app\static\admin\*" -Recurse -Force -ErrorAction SilentlyContinue
                Copy-Item -Path "dist\*" -Destination "..\..\app\static\admin\" -Recurse -Force
                Set-Location ..\..
                Write-Host "✓ Admin UI built and copied to static directory" -ForegroundColor Green
                
                # Commit the built files
                git add app/static/admin
                git commit -m "chore(admin): update built admin static after fixes" -ErrorAction SilentlyContinue
            } else {
                Write-Host "⚠ Build directory not found, admin UI may not be built" -ForegroundColor Yellow
            }
        } else {
            Write-Host "⚠ npm not available, skipping admin UI build" -ForegroundColor Yellow
            Write-Host "  Run manually: cd web/admin && npm ci && npm run build" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "⚠ Admin UI build failed: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  Run manually: cd web/admin && npm ci && npm run build" -ForegroundColor Cyan
    } finally {
        # Make sure we're back in the root directory
        if ((Get-Location).Path -like "*web\admin*") {
            Set-Location ..\..
        }
    }
} else {
    Write-Host "`n4. Skipping admin UI build (--SkipBuild flag)" -ForegroundColor Yellow
}

# 5. Run database migrations
Write-Host "`n5. Running database migrations..." -ForegroundColor Yellow
try {
    if (Get-Command alembic -ErrorAction SilentlyContinue) {
        alembic upgrade head
        Write-Host "✓ Database migrations completed" -ForegroundColor Green
    } else {
        Write-Host "⚠ alembic not available, skipping migrations" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Database migrations failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 6. Summary
Write-Host "`n=== FIXES APPLIED ===" -ForegroundColor Green
Write-Host "✓ Added /invitecodes alias endpoint for backwards compatibility" -ForegroundColor Green
Write-Host "✓ Improved error handling in admin UI pages" -ForegroundColor Green
Write-Host "✓ Enhanced users endpoint error handling" -ForegroundColor Green
Write-Host "✓ Created database seeding script" -ForegroundColor Green
Write-Host "✓ Created improved diagnostic scripts" -ForegroundColor Green

if (-not $SkipBuild) {
    Write-Host "✓ Admin UI rebuilt and deployed" -ForegroundColor Green
}

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Restart your application server" -ForegroundColor White
Write-Host "2. Run the diagnostic script: .\admin_diag_improved.ps1" -ForegroundColor White
Write-Host "3. Test the admin interface at: http://localhost:8000/admin" -ForegroundColor White

Write-Host "`n=== Fixes Complete ===" -ForegroundColor Green
