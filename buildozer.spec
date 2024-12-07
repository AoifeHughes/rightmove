[app]
title = Property Price Game
package.name = propertypricegame
package.domain = org.propertypricegame

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,db
source.include_patterns = assets/*,images/*
source.exclude_dirs = tests, bin, venv

version = 1.0

requirements = python3,\
    kivy,\
    pillow,\
    asyncio,\
    sqlite3

# iOS specific
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0

ios.codesign.allowed = false
ios.deployment_target = 13.0
ios.requirements = kivy,pillow,asyncio,sqlite3

orientation = portrait

fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
