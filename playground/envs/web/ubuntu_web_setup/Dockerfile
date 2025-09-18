# Use Ubuntu as base image
FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install X11, GUI components, and dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    python3-tk python3-dev \
    xvfb x11vnc xterm \
    fluxbox \
    scrot \
    chromium-browser \
    libgbm1 libx11-xcb1 libxcb-dri3-0 libxcomposite1 libxcursor1 \
    libxdamage1 libxfixes3 libxi6 libxtst6 libnss3 libcups2 \
    libxss1 libxrandr2 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libpangocairo-1.0-0 libgtk-3-0 \
    git wget curl \
    python3-xlib \
    thunar \
    x11-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python3 -m playwright install-deps
RUN python3 -m playwright install chromium

# Copy your script files
COPY ./scripts/ /app/scripts
COPY ./docker_entrypoint.sh /app/docker_entrypoint.sh
RUN chmod 777 -R /app

# Expose ports
EXPOSE 9000 5900

# Set entry point
ENTRYPOINT ["/app/docker_entrypoint.sh"]