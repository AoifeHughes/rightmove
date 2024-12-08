import os

from kivy.app import App
from propertypriceapp.kivy_app import PropertyGameApp

if __name__ == "__main__":
    if os.environ.get("KIVY_BUILD") == "ios":
        from pyobjus import autoclass

        NSURL = autoclass("NSURL")
        NSFileManager = autoclass("NSFileManager")

        # Set up iOS document directory for database
        fm = NSFileManager.defaultManager()
        urls = fm.URLsForDirectory_inDomains_(9, 1)
        url = urls.objectAtIndex_(0)
        os.environ["HOME"] = url.path()

    app = PropertyGameApp()
    app.run()
