#!/bin/bash

# CricAlgo Local Development Script
# Runs the FastAPI application locally with hot reload

set -o errexit
set -o nounset
set -o pipefail

echo "Starting CricAlgo local development server..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please update .env with your configuration before running again."
    exit 1
fi

# Run the application with uvicorn
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
