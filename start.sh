#!/bin/bash

# JARVIS Startup Script
# Run this to start your AI Assistant

JARVIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$JARVIS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$JARVIS_ROOT/logs"

echo "🥋 Starting JARVIS..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check dependencies
check_dep() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $2 installed"
        return 0
    else
        echo -e "${RED}✗${NC} $2 not found"
        return 1
    fi
}

echo -e "${BLUE}=== JARVIS System Check ===${NC}"

# Check core dependencies
check_dep node "Node.js"
check_dep python3 "Python"
check_dep docker "Docker"
check_dep git "Git"

echo ""
echo -e "${BLUE}=== Starting Services ===${NC}"

# Start Redis
if command -v redis-server &> /dev/null; then
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "Starting Redis..."
        redis-server --daemonize yes
    fi
    echo -e "${GREEN}✓${NC} Redis running"
fi

# Start Ollama in background
if command -v ollama &> /dev/null; then
    if ! pgrep -x "ollama" > /dev/null; then
        echo "Starting Ollama..."
        nohup ollama serve > "$JARVIS_ROOT/logs/ollama.log" 2>&1 &
        sleep 3
    fi
    echo -e "${GREEN}✓${NC} Ollama running"
fi

echo ""
echo -e "${BLUE}=== JARVIS Ready ===${NC}"
echo ""
echo "Good morning, sir. Systems are online and ready."
echo ""
echo "Commands:"
echo "  ./start.sh          - Start JARVIS"
echo "  ./jarvis voice    - Activate voice mode"
echo "  ./jarvis chat    - Chat in terminal"
echo "  ./jarvis status  - Check system status"
echo ""

# Make executable
chmod +x "$JARVIS_ROOT/jarvis" "$JARVIS_ROOT/jarvis.sh" 2>/dev/null || true