#!/bin/bash
set -e

# Install kivy-ios if not already installed
# pip install kivy-ios

# Build dependencies
toolchain build kivy
toolchain build python3
toolchain build matplotlib

# Create and build project
toolchain create PropertyPriceApp ~/git/rightmove
cd PropertyPriceApp
toolchain build ios
