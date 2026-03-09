#!/bin/bash

# Pipeline Guardian - Start Script

set -e

cd "$(dirname "$0")"

# Check for .env file
if [ ! -f .env ]; then
    echo "No .env file found. Creating from template..."
    cp .env.example .env
    echo "Please edit .env with your credentials, then run this script again."
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Check required variables
if [ -z "$JENKINS_URL" ]; then
    echo "Error: JENKINS_URL not set in .env"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -e .

# Start the server
echo ""
echo "Starting Pipeline Guardian..."
echo "Dashboard: http://localhost:8888"
echo ""

pg-server
