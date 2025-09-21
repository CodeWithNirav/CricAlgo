# CricAlgo Database Backup Script for Windows
# Run this script as Administrator to set up daily backups

param(
    [string]$BackupDir = "C:\backups\cricalgo",
    [int]$RetentionDays = 90
)

# Create backup directory if it doesn't exist
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force
    Write-Host "Created backup directory: $BackupDir"
}

# Function to create backup
function Backup-Database {
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
    $backupFile = Join-Path $BackupDir "cricalgo_$timestamp.dump"
    
    Write-Host "Creating database backup: $backupFile"
    
    # Use docker exec to run pg_dump
    docker exec cricalgo-postgres-1 pg_dump -U postgres -Fc --no-acl --no-owner cricalgo > $backupFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Backup created successfully: $backupFile"
        return $backupFile
    } else {
        Write-Error "Backup failed with exit code: $LASTEXITCODE"
        return $null
    }
}

# Function to clean old backups
function Remove-OldBackups {
    Write-Host "Cleaning backups older than $RetentionDays days..."
    
    $cutoffDate = (Get-Date).AddDays(-$RetentionDays)
    $oldBackups = Get-ChildItem -Path $BackupDir -Filter "cricalgo_*.dump" | Where-Object { $_.LastWriteTime -lt $cutoffDate }
    
    foreach ($backup in $oldBackups) {
        Write-Host "Removing old backup: $($backup.Name)"
        Remove-Item $backup.FullName -Force
    }
    
    Write-Host "Cleanup completed. Removed $($oldBackups.Count) old backups."
}

# Main execution
Write-Host "Starting CricAlgo database backup process..."
Write-Host "Backup directory: $BackupDir"
Write-Host "Retention period: $RetentionDays days"

# Check if PostgreSQL container is running
$postgresContainer = docker ps --filter "name=cricalgo-postgres-1" --format "{{.Names}}"
if ($postgresContainer -ne "cricalgo-postgres-1") {
    Write-Error "PostgreSQL container is not running. Please start the database first."
    exit 1
}

# Create backup
$backupFile = Backup-Database

if ($backupFile) {
    # Clean old backups
    Remove-OldBackups
    
    Write-Host "Backup process completed successfully!"
    Write-Host "Latest backup: $backupFile"
} else {
    Write-Error "Backup process failed!"
    exit 1
}
