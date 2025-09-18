# Use a Debian-based Python image as the base image
FROM python:3.11-slim-bullseye

# Optional: replace Debian APT sources with USTC mirror
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# Install Flask via Tsinghua PyPI mirror
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install flask

# Update package index and install essential tools and dependencies
RUN apt-get update && apt-get install -y \
    vim \
    wget \
    unzip \
    libpulse-dev \
    libnss3 \
    cpu-checker \
    # === Android Emulator and Qt related dependencies ===
    libdrm2 \
    libxkbfile1 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libglu1-mesa \
    libqt5gui5 \
    libqt5core5a \
    libqt5widgets5 \
    libqt5network5 \
    libqt5qml5 \
    libqt5quick5 \
    libx11-xcb-dev \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-glx0 \
    libsdl2-2.0-0 \
    libxext6 \
    libpciaccess0

# Create installation directory and switch to it
RUN mkdir -p /root/install-android && cd /root/install-android

# Copy and install OpenJDK package
COPY openlogic-openjdk-8u412-b08-linux-x64-deb.deb .
RUN apt install -y ./openlogic-openjdk-8u412-b08-linux-x64-deb.deb

# Set Android environment variables
ENV ANDROID_HOME=/root/.android
RUN mkdir -p $ANDROID_HOME

# Copy and unpack Android SDK tools
COPY sdk-tools-linux-4333796.zip .
RUN unzip ./sdk-tools-linux-4333796.zip -d $ANDROID_HOME

# Update .bashrc with Android SDK paths
RUN echo "export ANDROID_HOME=$ANDROID_HOME" >> /root/.bashrc \
    && echo 'export SDK=$ANDROID_HOME' >> /root/.bashrc \
    && echo 'export ANDROID_SDK_ROOT=$ANDROID_HOME' >> /root/.bashrc \
    && echo 'export PATH=$SDK/emulator:$SDK/tools:$SDK/tools/bin:$SDK/platform-tools:$PATH' >> /root/.bashrc

# Install Android SDK components
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'platform-tools' 'emulator'"
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'build-tools;33.0.0'"
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'platforms;android-33'"

# Unpack AVD skins and configuration
COPY skins.zip .
RUN unzip ./skins.zip -d /root/.android/ 
COPY Pixel_7_Pro_API_33.ini /root/.android/avd/
COPY Pixel_7_Pro_API_33.avd.zip .
RUN unzip ./Pixel_7_Pro_API_33.avd.zip -d /root/.android/avd/ 

# Copy adb client script
COPY adb_client.py /

# Install system image for emulator
COPY x86_64.zip .
RUN mkdir -p /root/.android/system-images/android-33/google_apis/
RUN unzip ./x86_64.zip -d /root/.android/system-images/android-33/google_apis/ 

# Clean up unnecessary files
RUN rm /Pixel_7_Pro_API_33.avd.zip \
    && rm /openlogic-openjdk-8u412-b08-linux-x64-deb.deb \
    && rm /sdk-tools-linux-4333796.zip \
    && rm /skins.zip \
    && rm /x86_64.zip
