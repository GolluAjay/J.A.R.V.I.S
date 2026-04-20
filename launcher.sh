#!/bin/bash
# JARVIS Auto-Launch Script
# Add to Login Items to start on boot

JARVIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$JARVIS_ROOT/logs/launch.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOGFILE"
}

# Check if already running
if pgrep -f "jarvis.cli" > /dev/null; then
    log "JARVIS already running"
    exit 0
fi

log "Starting JARVIS..."

# Start services
cd "$JARVIS_ROOT" || exit 1
export PYTHONPATH="$JARVIS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    nohup ollama serve >> "$JARVIS_ROOT/logs/ollama.log" 2>&1 &
    log "Started Ollama"
fi

# Start Redis if not running  
if ! pgrep -x "redis-server" > /dev/null; then
    redis-server --daemonize yes
    log "Started Redis"
fi

# Test Ollama
sleep 3
if curl -s http://localhost:11434/ > /dev/null 2>&1; then
    log "Ollama ready"
else
    log "Warning: Ollama not ready"
fi

# Greet user
say "JARVIS is online, sir."

log "JARVIS started successfully"
echo "🤖 JARVIS is online!"

# Keep running
while true; do
    sleep 60
done