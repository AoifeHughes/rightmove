#!/bin/bash

# Exit on error
set -e

echo "Setting up build environment for iOS..."

# Install Homebrew if not installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install required dependencies
echo "Installing dependencies..."
brew install autoconf automake libtool pkg-config
brew install python3
brew install git

# Install buildozer
echo "Installing buildozer..."
pip3 install buildozer

# Install Kivy dependencies
echo "Installing Kivy dependencies..."
pip3 install kivy-ios

# Create iOS build
echo "Building for iOS..."
buildozer ios debug

echo "Build complete! The .ipa file can be found in the bin directory."
echo "To install on your iPad:"
echo "1. Open Xcode"
echo "2. Window -> Devices and Simulators"
echo "3. Select your iPad"
echo "4. Drag and drop the .ipa file to the Installed Apps section"
