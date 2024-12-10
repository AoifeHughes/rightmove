import asyncio
import threading
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock

from database import PropertyDatabase
from data_getter import generate_random_properties

class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = PropertyDatabase()
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        # Add spacer at top
        layout.add_widget(Label(size_hint_y=0.3))

        # Title
        title = Label(text="Property Price Game", font_size="24sp", size_hint_y=0.2)
        layout.add_widget(title)

        # Buttons
        self.start_button = Button(
            text="Start",
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={"center_x": 0.5},
        )
        self.start_button.bind(on_press=self.start_game)

        generate_button = Button(
            text="Generate new data",
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={"center_x": 0.5},
        )
        generate_button.bind(on_press=self.generate_data)

        layout.add_widget(self.start_button)
        layout.add_widget(Label(size_hint_y=0.1))  # Spacer
        layout.add_widget(generate_button)

        # Add spacer at bottom
        layout.add_widget(Label(size_hint_y=0.3))

        self.add_widget(layout)

        # Check database status when screen is created
        self.check_database_status()

    def check_database_status(self):
        """Check if there are enough properties in the database"""
        count = self.db.count_properties()
        if count < 10:  # Need at least 10 properties for a game
            self.start_button.disabled = True
            self.start_button.text = "Need more properties"
        else:
            self.start_button.disabled = False
            self.start_button.text = "Start"

    def start_game(self, instance):
        # Double check database status before starting
        count = self.db.count_properties()
        if count < 10:
            self.manager.current = "loading"
            self.start_generation()
            return

        self.manager.get_screen("game").load_properties()
        self.manager.current = "game"

    def generate_data(self, instance):
        self.manager.current = "loading"
        self.start_generation()

    def update_progress(self, progress):
        """Update the loading screen progress"""
        loading_screen = self.manager.get_screen("loading")
        loading_screen.progress_bar.value = progress

    def generation_complete(self, *args):
        """Called when generation is complete"""
        loading_screen = self.manager.get_screen("loading")
        loading_screen.status_label.text = "Generation complete!"
        self.check_database_status()
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "menu"), 1)

    def generation_error(self, error):
        """Called when generation encounters an error"""
        loading_screen = self.manager.get_screen("loading")
        loading_screen.status_label.text = f"Error: {str(error)}"
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "menu"), 3)

    def start_generation(self):
        """Start property generation in a non-blocking way"""
        loading_screen = self.manager.get_screen("loading")
        loading_screen.status_label.text = "Generating new properties..."
        loading_screen.progress_bar.value = 0

        async def generation_task():
            try:
                await generate_random_properties(10, self.db, self.update_progress)
                Clock.schedule_once(self.generation_complete)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.generation_error(str(e)))

        # Run the async task in a separate thread
        def run_async_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generation_task())
            loop.close()

        thread = threading.Thread(target=run_async_task)
        thread.daemon = True
        thread.start()
