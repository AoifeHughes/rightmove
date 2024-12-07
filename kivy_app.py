from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.scrollview import ScrollView
import json
import random
from pathlib import Path
import asyncio
from main import generate_random_properties

class PropertyGame(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.properties = []
        self.current_property = None
        self.current_image_index = 0
        self.score = 0
        self.guesses_remaining = 5
        self.revealed_info = []
        
        # Main content area (left side)
        main_content = BoxLayout(orientation='vertical', size_hint_x=0.7)
        
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
            disabled=True  # Initially disabled until properties are loaded
        )
        guess_controls.add_widget(self.price_input)
        guess_controls.add_widget(self.submit_btn)
        main_content.add_widget(guess_controls)
        
        # Result label
        self.result_label = Label(text='', size_hint_y=0.1)
        main_content.add_widget(self.result_label)
        
        self.add_widget(main_content)
        
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
        # Bind the width to ensure text wrapping
        def update_text_width(instance, value):
            self.info_label.text_size = (value * 0.9, None)  # 90% of the scroll view width
            
        scroll_view.bind(width=update_text_width)
        self.info_label.bind(texture_size=self.info_label.setter('size'))
        scroll_view.add_widget(self.info_label)
        info_panel.add_widget(scroll_view)
        
        self.add_widget(info_panel)
        
        # Keyboard binding
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        
        # Start property generation
        Clock.schedule_once(self.generate_properties, 0)

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
            self.guesses_remaining = 5
            self.guesses_label.text = f'Guesses remaining: {self.guesses_remaining}'
            
            # Reset and show initial information
            self.revealed_info = self.get_initial_info()
            self.update_info_panel()
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
            
            # Check if guess is correct (within 5%)
            if difference <= 5:
                points = self.guesses_remaining + 1
                self.score += points
                self.score_label.text = f'Score: {self.score}'
                self.result_label.text = f'Correct! You got {points} points! Actual price: £{actual_price:,.0f}'
                self.properties.remove(self.current_property)
                self.remaining_label.text = f'Properties remaining: {len(self.properties)}'
                self.submit_btn.disabled = True
            else:
                # Provide feedback on the guess
                feedback = "Too high!" if guess > actual_price else "Too low!"
                if abs(guess - actual_price) > actual_price:  # More than 2x different
                    feedback += " (More than 2x different!)"
                
                if self.guesses_remaining > 0:
                    self.result_label.text = f'{feedback} Try again!'
                else:
                    self.result_label.text = f'Game over! The actual price was £{actual_price:,.0f}'
                    self.submit_btn.disabled = True
                
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
