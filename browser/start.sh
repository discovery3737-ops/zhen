#!/bin/sh
set -e
Xvfb :99 -screen 0 1920x1080x24 &
sleep 2
fluxbox &
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
sleep 2
websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 2
chromium --no-sandbox --remote-debugging-address=0.0.0.0 --remote-debugging-port=9222 --window-size=1920,1080 &
wait
