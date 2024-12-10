from kivy.app import App
from kivy.uix.screenmanager import ScreenManager

from screens.loading_screen import LoadingScreen
from screens.menu_screen import MenuScreen
from screens.property_game import PropertyGame

class PropertyGameApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._running = True

    def build(self):
        sm = ScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(LoadingScreen(name="loading"))
        sm.add_widget(PropertyGame(name="game"))
        return sm

    def stop(self, *largs):
        self._running = False
        return super(PropertyGameApp, self).stop(*largs)

    def on_stop(self):
        self._running = False
