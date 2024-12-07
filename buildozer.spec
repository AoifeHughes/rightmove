# buildozer.spec
[app]
title = Property Price Game
package.name = propertypriceapp
package.domain = org.propertypriceapp
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,sqlite3,httpx,asyncio,jmespath,parsel,geopandas,matplotlib,shapely

# iOS specific
ios.kivy_ios_dir = $(SRCROOT)/kivy-ios
ios.codesign.allowed = false
ios.deployment_target = 13.0
ios.devices = tablet
