from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen

class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        self.status_label = Label(text="Loading properties...", size_hint_y=0.1)
        self.progress_bar = ProgressBar(max=100, size_hint_y=0.1)

        layout.add_widget(Label(size_hint_y=0.4))  # Spacer
        layout.add_widget(self.status_label)
        layout.add_widget(self.progress_bar)
        layout.add_widget(Label(size_hint_y=0.4))  # Spacer

        self.add_widget(layout)
