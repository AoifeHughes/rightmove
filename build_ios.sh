#!/bin/bash

# Exit on error
set -e

echo "Setting up build environment for iOS..."

# Set up environment
toolchain build python3 kivy
toolchain build hostpython3
toolchain build ios
toolchain build sqlite3
toolchain build matplotlib

# Build the app
toolchain create PropertyPriceApp ~/git/rightmove
open PropertyPriceApp/ios/build/PropertyPriceApp.xcodeproj