from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, DeferredList
import json
import random
from pathlib import Path
from main import generate_random_properties
from database import PropertyDatabase

class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        self.status_label = Label(
            text='Loading properties...',
            size_hint_y=0.1
        )
        self.progress_bar = ProgressBar(
            max=100,
            size_hint_y=0.1
        )
        
        layout.add_widget(Label(size_hint_y=0.4))  # Spacer
        layout.add_widget(self.status_label)
        layout.add_widget(self.progress_bar)
        layout.add_widget(Label(size_hint_y=0.4))  # Spacer
        
        self.add_widget(layout)

class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = PropertyDatabase()
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # Add spacer at top
        layout.add_widget(Label(size_hint_y=0.3))
        
        # Title
        title = Label(
            text='Property Price Game',
            font_size='24sp',
            size_hint_y=0.2
        )
        layout.add_widget(title)
        
        # Buttons
        self.start_button = Button(
            text='Start',
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={'center_x': 0.5}
        )
        self.start_button.bind(on_press=self.start_game)
        
        generate_button = Button(
            text='Generate new data',
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={'center_x': 0.5}
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
            self.start_button.text = 'Need more properties'
        else:
            self.start_button.disabled = False
            self.start_button.text = 'Start'
    
    def start_game(self, instance):
        # Double check database status before starting
        count = self.db.count_properties()
        if count < 10:
            self.manager.current = 'loading'
            self.start_generation()
            return
            
        self.manager.get_screen('game').load_properties()
        self.manager.current = 'game'
    
    def generate_data(self, instance):
        self.manager.current = 'loading'
        self.start_generation()
    
    def start_generation(self):
        loading_screen = self.manager.get_screen('loading')
        loading_screen.status_label.text = 'Generating new properties...'
        loading_screen.progress_bar.value = 0
        
        db = PropertyDatabase()
        
        def update_progress(result, i):
            loading_screen.progress_bar.value = (i + 1) * 10
            return result
        
        def generation_complete(results):
            loading_screen.status_label.text = 'Generation complete!'
            self.check_database_status()  # Update button status
            Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'menu'), 1)
        
        def generation_error(error):
            loading_screen.status_label.text = f'Error: {str(error)}'
            Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'menu'), 3)
        
        # Generate one property at a time to show progress
        d = generate_random_properties(1, db)
        for i in range(9):  # Generate 9 more for a total of 10
            d.addCallback(lambda _, i=i: update_progress(_, i))
            d.addCallback(lambda _: generate_random_properties(1, db))
        
        d.addCallback(update_progress, 9)  # Update progress for the last property
        d.addCallback(generation_complete)
        d.addErrback(generation_error)

class PropertyGame(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.db = PropertyDatabase()
        self.properties = []
        self.current_property = None
        self.current_image_index = 0
        self.score = 0
        self.guesses_remaining = 5
        self.revealed_info = []
        
        # Main layout
        main_layout = BoxLayout(orientation='horizontal')
        
        # Main content area (left side)
        main_content = BoxLayout(orientation='vertical', size_hint_x=0.7)
        
        # Top controls
        top_controls = BoxLayout(size_hint_y=0.1)
        self.remaining_label = Label(
            text='Properties remaining: 0',
            size_hint_x=0.3
        )
        self.score_label = Label(
            text=f'Score: {self.score}',
            size_hint_x=0.3
        )
        self.random_btn = Button(
            text='Next Property',
            size_hint_x=0.4,
            on_press=self.load_random_property,
            disabled=True
        )
        top_controls.add_widget(self.remaining_label)
        top_controls.add_widget(self.score_label)
        top_controls.add_widget(self.random_btn)
        main_content.add_widget(top_controls)
        
        # Image display and counter
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        main_content.add_widget(self.image_widget)
        self.image_counter = Label(text='', size_hint_y=0.1)
        main_content.add_widget(self.image_counter)
        
        # Guesses remaining label
        self.guesses_label = Label(
            text=f'Guesses remaining: {self.guesses_remaining}',
            size_hint_y=0.1
        )
        main_content.add_widget(self.guesses_label)
        
        # Price guess controls
        guess_controls = BoxLayout(size_hint_y=0.1)
        self.price_input = TextInput(
            multiline=False,
            size_hint_x=0.7,
            hint_text='Enter price guess (e.g. 250000)'
        )
        self.submit_btn = Button(
            text='Submit Guess',
            size_hint_x=0.3,
            on_press=self.check_guess,
            disabled=True
        )
        guess_controls.add_widget(self.price_input)
        guess_controls.add_widget(self.submit_btn)
        main_content.add_widget(guess_controls)
        
        # Result label
        self.result_label = Label(text='', size_hint_y=0.1)
        main_content.add_widget(self.result_label)
        
        main_layout.add_widget(main_content)
        
        # Property info panel (right side)
        info_panel = BoxLayout(orientation='vertical', size_hint_x=0.3, padding=10)
        info_panel.add_widget(Label(text='Property Information', size_hint_y=0.1))
        
        # Scrollable info area
        scroll_view = ScrollView(size_hint_y=0.9)
        self.info_label = Label(
            text='',
            size_hint_y=None,
            markup=True,
            halign='left',
            valign='top',
            padding=(10, 10)
        )
        
        def update_text_width(instance, value):
            self.info_label.text_size = (value * 0.9, None)
        
        scroll_view.bind(width=update_text_width)
        self.info_label.bind(texture_size=self.info_label.setter('size'))
        scroll_view.add_widget(self.info_label)
        info_panel.add_widget(scroll_view)
        
        main_layout.add_widget(info_panel)
        
        self.add_widget(main_layout)
        
        # Keyboard binding
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
    
    def load_properties(self):
        """Load properties from database"""
        # Check if we have enough unused properties
        property_data = self.db.get_random_unused_properties(10)
        if not property_data:
            # If no unused properties, reset all properties to unused
            self.db.reset_used_status()
            # Try to get properties again
            property_data = self.db.get_random_unused_properties(10)
        
        self.properties = [(data, images_dir) for data, images_dir in property_data]
        self.remaining_label.text = f'Properties remaining: {len(self.properties)}'
        if self.properties:
            self.random_btn.disabled = False
            self.submit_btn.disabled = False
            self.load_random_property(None)
        else:
            self.result_label.text = 'No more properties available!'
            Clock.schedule_once(lambda dt: self.return_to_menu(), 2)
    
    def return_to_menu(self):
        self.manager.current = 'menu'
    
    def get_initial_info(self):
        """Return the initial property information to show"""
        return [
            f"[b]Location:[/b] {self.current_property['address']['displayAddress']}",
            f"[b]Property Type:[/b] {self.current_property['property_type']}"
        ]
    
    def get_progressive_info(self):
        """Return information to reveal progressively with each guess"""
        info_stages = [
            [f"[b]Bedrooms:[/b] {self.current_property['bedrooms']}"],
            [f"[b]Bathrooms:[/b] {self.current_property['bathrooms']}"],
            [f"[b]Size:[/b] {next((f'{s['max']} {s['unit']}' for s in self.current_property['sizings'] if s['unit'] == 'sqm'), 'Not specified')}"],
            [f"[b]Key Features:[/b]"] + [f"• {feature}" for feature in self.current_property['features']]
        ]
        return info_stages
    
    def update_info_panel(self):
        """Update the information panel with current revealed info"""
        if not self.current_property:
            return
        
        info_text = '\n\n'.join(self.revealed_info)
        self.info_label.text = info_text
    
    def load_random_property(self, instance):
        if self.properties:
            self.current_property, self.current_images_dir = self.properties.pop(0)
            self.current_image_index = 0
            self.price_input.text = ''
            self.result_label.text = ''
            self.guesses_remaining = 5
            self.guesses_label.text = f'Guesses remaining: {self.guesses_remaining}'
            self.remaining_label.text = f'Properties remaining: {len(self.properties)}'
            
            # Reset and show initial information
            self.revealed_info = self.get_initial_info()
            self.update_info_panel()
            self.update_display()
    
    def update_display(self):
        if not self.current_property:
            return
        
        images_dir = Path(self.current_images_dir) / "images"
        image_files = sorted([f for f in images_dir.glob("photo_*.jpg")])
        if image_files and 0 <= self.current_image_index < len(image_files):
            self.image_widget.source = str(image_files[self.current_image_index])
            self.image_counter.text = f'Image {self.current_image_index + 1}/{len(image_files)}'
    
    def check_guess(self, instance):
        if not self.current_property or self.guesses_remaining <= 0:
            return
        
        try:
            guess = float(self.price_input.text)
            actual_price = float(self.current_property['price'].replace('£', '').replace(',', ''))
            
            difference = abs(guess - actual_price) / actual_price * 100
            
            # Reveal more information
            info_stages = self.get_progressive_info()
            stage_index = 5 - self.guesses_remaining
            if stage_index < len(info_stages):
                self.revealed_info.extend(info_stages[stage_index])
                self.update_info_panel()
            
            self.guesses_remaining -= 1
            self.guesses_label.text = f'Guesses remaining: {self.guesses_remaining}'
            
            if difference <= 5:
                points = self.guesses_remaining + 1
                self.score += points
                self.score_label.text = f'Score: {self.score}'
                self.result_label.text = f'Correct! You got {points} points! Actual price: £{actual_price:,.0f}'
                if not self.properties:
                    Clock.schedule_once(lambda dt: self.return_to_menu(), 2)
            else:
                feedback = "Too high!" if guess > actual_price else "Too low!"
                if abs(guess - actual_price) > actual_price:
                    feedback += " (More than 2x different!)"
                
                if self.guesses_remaining > 0:
                    self.result_label.text = f'{feedback} Try again!'
                else:
                    self.result_label.text = f'Game over! The actual price was £{actual_price:,.0f}'
                    if not self.properties:
                        Clock.schedule_once(lambda dt: self.return_to_menu(), 2)
        
        except ValueError:
            self.result_label.text = 'Please enter a valid number'
    
    def _on_key_down(self, keyboard, keycode, text, modifiers):
        if not self.current_property:
            return True
        
        if keycode[1] == 'left':
            if self.current_image_index > 0:
                self.current_image_index -= 1
                self.update_display()
        elif keycode[1] == 'right':
            images_dir = Path(self.current_images_dir) / "images"
            image_count = len(list(images_dir.glob("photo_*.jpg")))
            if self.current_image_index < image_count - 1:
                self.current_image_index += 1
                self.update_display()
        return True
    
    def _on_keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_key_down)
        self._keyboard = None

class PropertyGameApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._running = True
        self._shutdown_attempted = False
        
        def cleanup_reactor():
            if reactor.running:
                try:
                    reactor.stop()
                except:
                    pass
        atexit.register(cleanup_reactor)

    def build(self):
        sm = ScreenManager()
        sm.add_widget(MenuScreen(name='menu'))
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(PropertyGame(name='game'))
        return sm

    def stop(self, *largs):
        if self._shutdown_attempted:
            return True
        self._shutdown_attempted = True
        self._running = False

        # Stop the Twisted reactor gracefully if it's running
        if reactor.running:
            try:
                Clock.schedule_once(lambda dt: reactor.callFromThread(reactor.stop), 0)
            except Exception as e:
                print(f"Error stopping reactor: {e}")
                pass

        return super(PropertyGameApp, self).stop(*largs)

    def on_stop(self):
        self._running = False

if __name__ == '__main__':
    import atexit
    
    def run_app():
        try:
            app = PropertyGameApp()
            app.run()
        except Exception as e:
            print(f"Error during app execution: {e}")
            if reactor.running:
                try:
                    reactor.callFromThread(reactor.stop)
                except:
                    pass
    
    run_app()