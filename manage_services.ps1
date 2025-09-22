#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Simple script to start and stop CricAlgo services

.DESCRIPTION
    This script provides easy commands to start, stop, and restart the CricAlgo application services including the database, Redis, and application server.

.PARAMETER Action
    The action to perform: start, stop, restart, status, logs

.EXAMPLE
    .\manage_services.ps1 start
    .\manage_services.ps1 stop
    .\manage_services.ps1 restart
    .\manage_services.ps1 status
    .\manage_services.ps1 logs
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "restart", "status", "logs")]
    [string]$Action
)

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Start-Services {
    Write-ColorOutput "🚀 Starting CricAlgo services..." "Green"
    
    # Start all services
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✅ Services started successfully!" "Green"
        Write-ColorOutput "📊 Checking service status..." "Yellow"
        Start-Sleep -Seconds 5
        Show-Status
    } else {
        Write-ColorOutput "❌ Failed to start services" "Red"
        exit 1
    }
}

function Stop-Services {
    Write-ColorOutput "🛑 Stopping CricAlgo services..." "Yellow"
    
    # Stop all services
    docker-compose down
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "✅ Services stopped successfully!" "Green"
    } else {
        Write-ColorOutput "❌ Failed to stop services" "Red"
        exit 1
    }
}

function Restart-Services {
    Write-ColorOutput "🔄 Restarting CricAlgo services..." "Cyan"
    
    # Stop services first
    Stop-Services
    Start-Sleep -Seconds 2
    
    # Start services
    Start-Services
}

function Show-Status {
    Write-ColorOutput "📊 Service Status:" "Cyan"
    Write-Host ""
    
    # Show container status
    docker-compose ps
    
    Write-Host ""
    Write-ColorOutput "🌐 Service URLs:" "Cyan"
    Write-ColorOutput "   Admin Dashboard: http://localhost:8000/admin" "White"
    Write-ColorOutput "   API Docs: http://localhost:8000/docs" "White"
    Write-ColorOutput "   Health Check: http://localhost:8000/api/v1/health" "White"
    Write-ColorOutput "   Database: localhost:5432" "White"
    Write-ColorOutput "   Redis: localhost:6379" "White"
}

function Show-Logs {
    Write-ColorOutput "📋 Showing recent logs..." "Cyan"
    Write-Host ""
    
    # Show logs for all services
    docker-compose logs --tail=20
}

# Main script logic
switch ($Action) {
    "start" {
        Start-Services
    }
    "stop" {
        Stop-Services
    }
    "restart" {
        Restart-Services
    }
    "status" {
        Show-Status
    }
    "logs" {
        Show-Logs
    }
}

Write-Host ""
Write-ColorOutput "💡 Usage: .\manage_services.ps1 [start|stop|restart|status|logs]" "Gray"