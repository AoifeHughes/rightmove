from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
import json
import random
from pathlib import Path
import asyncio
from main import generate_random_properties

class PropertyGame(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.properties = []
        self.current_property = None
        self.current_image_index = 0
        self.score = 0
        
        # Top controls
        top_controls = BoxLayout(size_hint_y=0.1)
        self.remaining_label = Label(
            text='Generating properties...',
            size_hint_x=0.3
        )
        self.score_label = Label(
            text=f'Score: {self.score}',
            size_hint_x=0.3
        )
        self.random_btn = Button(
            text='Random Property',
            size_hint_x=0.4,
            on_press=self.load_random_property,
            disabled=True  # Initially disabled until properties are loaded
        )
        top_controls.add_widget(self.remaining_label)
        top_controls.add_widget(self.score_label)
        top_controls.add_widget(self.random_btn)
        self.add_widget(top_controls)
        
        # Image display and counter
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        self.add_widget(self.image_widget)
        self.image_counter = Label(text='', size_hint_y=0.1)
        self.add_widget(self.image_counter)
        
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
            disabled=True  # Initially disabled until properties are loaded
        )
        guess_controls.add_widget(self.price_input)
        guess_controls.add_widget(self.submit_btn)
        self.add_widget(guess_controls)
        
        # Result label
        self.result_label = Label(text='', size_hint_y=0.1)
        self.add_widget(self.result_label)
        
        # Keyboard binding
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        
        # Start property generation
        Clock.schedule_once(self.generate_properties, 0)

    async def async_generate_properties(self):
        """Generate properties asynchronously"""
        self.properties = await generate_random_properties(10)
        return self.properties

    def generate_properties(self, dt):
        """Start the property generation process"""
        async def start_generation():
            await self.async_generate_properties()
            # Update UI after properties are generated
            self.remaining_label.text = f'Properties remaining: {len(self.properties)}'
            self.random_btn.disabled = False
            self.submit_btn.disabled = False
            if self.properties:
                self.load_random_property(None)

        # Create and run the asyncio event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_generation())

    def load_random_property(self, instance):
        if self.properties:
            self.current_property = random.choice(self.properties)
            self.current_image_index = 0
            self.price_input.text = ''
            self.result_label.text = ''
            self.update_display()

    def update_display(self):
        if not self.current_property:
            return
            
        property_dir = Path("rightmove_data")
        # Find the most recent directory for this property ID
        matching_dirs = list(property_dir.glob(f"{self.current_property['id']}_*"))
        if not matching_dirs:
            return
            
        latest_dir = max(matching_dirs, key=lambda x: x.name.split('_')[1])
        images_dir = latest_dir / "images"
        
        image_files = sorted([f for f in images_dir.glob("photo_*.png")])
        if image_files and 0 <= self.current_image_index < len(image_files):
            self.image_widget.source = str(image_files[self.current_image_index])
            self.image_counter.text = f'Image {self.current_image_index + 1}/{len(image_files)}'
    
    def check_guess(self, instance):
        if not self.current_property:
            return
            
        try:
            guess = float(self.price_input.text)
            actual_price = float(self.current_property['price'].replace('£', '').replace(',', ''))
            
            difference = abs(guess - actual_price) / actual_price * 100
            
            if difference <= 5:
                self.score += 1
                self.score_label.text = f'Score: {self.score}'
                self.result_label.text = f'Correct! Actual price: £{actual_price:,.0f}'
                self.properties.remove(self.current_property)
                self.remaining_label.text = f'Properties remaining: {len(self.properties)}'
            else:
                self.result_label.text = 'Try again! (within 5%)'
                
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
            property_dir = Path("rightmove_data")
            matching_dirs = list(property_dir.glob(f"{self.current_property['id']}_*"))
            if matching_dirs:
                latest_dir = max(matching_dirs, key=lambda x: x.name.split('_')[1])
                images_dir = latest_dir / "images"
                image_count = len(list(images_dir.glob("photo_*.png")))
                if self.current_image_index < image_count - 1:
                    self.current_image_index += 1
                    self.update_display()
        return True

    def _on_keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_key_down)
        self._keyboard = None

class PropertyGameApp(App):
    def build(self):
        return PropertyGame()

if __name__ == '__main__':
    PropertyGameApp().run()
