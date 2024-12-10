import os

from kivy.app import App

from app.property_game_app import PropertyGameApp

if __name__ == "__main__":
    if os.environ.get("KIVY_BUILD") == "ios":
        app = PropertyGameApp()
        # Set the home directory to the iOS app's Documents directory
        os.environ["HOME"] = App.get_running_app().user_data_dir
        # You might also want to set the current working directory
        os.chdir(os.environ["HOME"])
        app.run()
