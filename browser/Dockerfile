# Chromium + noVNC + CDP for M1 授权闭环
FROM mcr.microsoft.com/playwright:v1.49.0-noble

USER root

RUN apt-get update && apt-get install -y \
    xvfb x11vnc novnc websockify fluxbox chromium \
    && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99
ENV SCREEN=1920x1080x24

COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 6080 9222

CMD ["/start.sh"]
