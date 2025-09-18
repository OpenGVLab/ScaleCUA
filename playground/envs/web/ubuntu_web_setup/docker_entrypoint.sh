#!/bin/bash

# Clean up old X server instances and lock files
rm -f /tmp/.X*-lock /tmp/.X11-unix/X*

# Create a new random MIT-MAGIC-COOKIE
COOKIE=$(mcookie)
echo "Generated cookie: $COOKIE"

# Prepare .Xauthority file
touch ~/.Xauthority
xauth -f ~/.Xauthority add :1 MIT-MAGIC-COOKIE-1 $COOKIE

# Start Xvfb
Xvfb :1 -screen 0 1920x1080x24 -auth ~/.Xauthority &
XVFB_PID=$!

# Wait for Xvfb to start
echo "Waiting for Xvfb to start..."
sleep 3

# Verify Xvfb is running
if ! ps -p $XVFB_PID > /dev/null; then
  echo "ERROR: Xvfb failed to start"
  exit 1
fi

# Ensure Xvfb socket exists
if [ ! -e /tmp/.X11-unix/X1 ]; then
  echo "ERROR: Xvfb socket not found"
  exit 1
fi

# Set DISPLAY environment variable
export DISPLAY=:1

# Test X connection
echo "Testing X connection..."
xdpyinfo > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "ERROR: Cannot connect to X server"
  exit 1
fi

echo "X server is running successfully"

# Start window manager
fluxbox &

# Start VNC server
x11vnc -display $DISPLAY -nopw -forever -shared &

# Run main program
export XLIB_SKIP_ARGB_VISUALS=1
export NO_AT_BRIDGE=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

echo "Starting main application..."
python3 /app/scripts/start.py