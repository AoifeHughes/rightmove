import io

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from database import PropertyDatabase


class PropertyGame(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.db = PropertyDatabase()
        self.properties = []
        self.current_property = None
        self.current_images = []
        self.current_image_index = 0
        self.score = 0
        self.guesses_remaining = 5
        self.revealed_info = []

        # Initialize UI components
        self.setup_ui()

    def setup_ui(self):
        """Create and organize all UI elements"""
        main_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Top row with score and remaining properties
        top_row = BoxLayout(size_hint_y=0.1)
        self.remaining_label = Label(text="Properties remaining: 0", size_hint_x=0.5)
        self.score_label = Label(text=f"Score: {self.score}", size_hint_x=0.5)
        top_row.add_widget(self.remaining_label)
        top_row.add_widget(self.score_label)
        main_layout.add_widget(top_row)

        # Guess controls at the bottom
        guess_section = BoxLayout(orientation="vertical", size_hint_y=0.1, spacing=5)
        self.guesses_label = Label(text=f"Guesses remaining: {self.guesses_remaining}")
        guess_section.add_widget(self.guesses_label)

        guess_input_row = BoxLayout(spacing=5)
        self.price_input = TextInput(
            multiline=False,
            size_hint_x=0.7,
            hint_text="Enter price guess (e.g. 250000)",
            input_type="number",
        )
        self.submit_btn = Button(
            text="Submit Guess",
            size_hint_x=0.3,
            on_press=self.check_guess,
            disabled=True,
        )
        guess_input_row.add_widget(self.price_input)
        guess_input_row.add_widget(self.submit_btn)
        guess_section.add_widget(guess_input_row)

        self.result_label = Label(text="")
        guess_section.add_widget(self.result_label)
        main_layout.add_widget(guess_section)

        # Button row with Next Property and Main Menu
        button_row = BoxLayout(size_hint_y=0.1)
        self.random_btn = Button(
            text="Next Property",
            size_hint_x=0.5,
            on_press=self.load_random_property,
            disabled=True,
        )
        self.menu_btn = Button(
            text="Main Menu", size_hint_x=0.5, on_press=self.return_to_menu
        )

        # Image gallery
        image_area = BoxLayout(orientation="vertical", size_hint_y=0.4)
        self.image_widget = Image(allow_stretch=True, keep_ratio=True)
        image_area.add_widget(self.image_widget)

        # Navigation controls
        nav_buttons = BoxLayout(size_hint_y=0.2, spacing=10)
        self.prev_button = Button(
            text="<", on_press=lambda x: self.change_image("left"), size_hint_x=0.5
        )
        self.next_button = Button(
            text=">", on_press=lambda x: self.change_image("right"), size_hint_x=0.5
        )
        nav_buttons.add_widget(self.prev_button)
        nav_buttons.add_widget(self.next_button)
        image_area.add_widget(nav_buttons)

        # Image counter
        self.image_counter = Label(text="", size_hint_y=0.1)
        image_area.add_widget(self.image_counter)
        main_layout.add_widget(image_area)

        # Information panel
        info_panel = BoxLayout(orientation="vertical", size_hint_y=0.3)
        info_panel.add_widget(Label(text="Property Information", size_hint_y=0.1))
        scroll_view = ScrollView()
        self.info_label = Label(
            text="",
            size_hint_y=None,
            markup=True,
            halign="left",
            valign="top",
            padding=(10, 10),
        )

        def update_text_width(instance, value):
            self.info_label.text_size = (value * 0.9, None)

        scroll_view.bind(width=update_text_width)
        self.info_label.bind(texture_size=self.info_label.setter("size"))
        scroll_view.add_widget(self.info_label)
        info_panel.add_widget(scroll_view)
        main_layout.add_widget(info_panel)

        button_row.add_widget(self.random_btn)
        button_row.add_widget(self.menu_btn)
        main_layout.add_widget(button_row)

        self.add_widget(main_layout)

    def change_image(self, direction):
        """Handle image navigation"""
        if not self.current_property:
            return

        if direction == "left" and self.current_image_index > 0:
            self.current_image_index -= 1
            self.update_display()
        elif (
            direction == "right"
            and self.current_image_index < len(self.current_images) - 1
        ):
            self.current_image_index += 1
            self.update_display()

    def load_properties(self):
        """Load properties from database"""
        property_data = self.db.get_random_unused_properties(10)
        if not property_data:
            # If no unused properties, reset all properties to unused
            self.db.reset_used_status()
            # Try to get properties again
            property_data = self.db.get_random_unused_properties(10)

        self.properties = property_data
        self.remaining_label.text = f"Properties remaining: {len(self.properties)}"
        if self.properties:
            self.random_btn.disabled = False
            self.submit_btn.disabled = False
            self.load_random_property(None)
        else:
            self.result_label.text = "No more properties available!"
            Clock.schedule_once(lambda dt: self.return_to_menu(), 2)

    def return_to_menu(self, *args):
        self.manager.current = "menu"

    def get_initial_info(self):
        """Return the initial property information to show"""
        return [
            f"[b]Location:[/b] {self.current_property['address']['displayAddress']}",
            f"[b]Property Type:[/b] {self.current_property['property_type']}",
        ]

    def get_progressive_info(self):
        """Return information to reveal progressively with each guess"""

        def get_size_info():
            for s in self.current_property.get("sizings", []):
                if s.get("unit") == "sqm":
                    return f"{s.get('max')} {s.get('unit')}"
            return "Not specified"

        info_stages = [
            [f"[b]Bedrooms:[/b] {self.current_property['bedrooms']}"],
            [f"[b]Bathrooms:[/b] {self.current_property['bathrooms']}"],
            [f"[b]Size:[/b] {get_size_info()}"],
            [f"[b]Key Features:[/b]"]
            + [f"• {feature}" for feature in self.current_property.get("features", [])],
        ]

        return info_stages

    def update_info_panel(self):
        """Update the information panel with current revealed info"""
        if not self.current_property:
            return

        info_text = "\n\n".join(self.revealed_info)
        self.info_label.text = info_text

    def load_random_property(self, instance):
        if self.properties:
            self.current_property, images, plot = self.properties.pop(0)
            # Insert plot as first image if it exists
            self.current_images = []
            if plot:
                self.current_images.append(plot)
            self.current_images.extend(images)

            self.current_image_index = 0
            self.price_input.text = ""
            self.result_label.text = ""
            self.guesses_remaining = 5
            self.guesses_label.text = f"Guesses remaining: {self.guesses_remaining}"
            self.remaining_label.text = f"Properties remaining: {len(self.properties)}"

            # Reset and show initial information
            self.revealed_info = self.get_initial_info()
            self.update_info_panel()
            self.update_display()

    def update_display(self):
        if not self.current_property:
            return

        # Update property image
        if self.current_images and 0 <= self.current_image_index < len(
            self.current_images
        ):
            image_data = self.current_images[self.current_image_index]
            image = CoreImage(
                io.BytesIO(image_data),
                ext="png" if self.current_image_index == 0 else "jpg",
            )
            self.image_widget.texture = image.texture
            self.image_counter.text = (
                f"Image {self.current_image_index + 1}/{len(self.current_images)}"
            )

            # Update navigation button states
            self.prev_button.disabled = self.current_image_index == 0
            self.next_button.disabled = (
                self.current_image_index >= len(self.current_images) - 1
            )

    def check_guess(self, instance):
        if not self.current_property or self.guesses_remaining <= 0:
            return

        try:
            guess = float(self.price_input.text)
            actual_price = float(
                self.current_property["price"].replace("£", "").replace(",", "")
            )

            difference = abs(guess - actual_price) / actual_price * 100

            # Reveal more information
            info_stages = self.get_progressive_info()
            stage_index = 5 - self.guesses_remaining
            if stage_index < len(info_stages):
                self.revealed_info.extend(info_stages[stage_index])
                self.update_info_panel()

            self.guesses_remaining -= 1
            self.guesses_label.text = f"Guesses remaining: {self.guesses_remaining}"

            if difference <= 5:
                points = self.guesses_remaining + 1
                self.score += points
                self.score_label.text = f"Score: {self.score}"
                self.result_label.text = f"Correct! You got {points} points! Actual price: £{actual_price:,.0f}"
                if not self.properties:
                    Clock.schedule_once(lambda dt: self.return_to_menu(), 2)
            else:
                feedback = "Too high!" if guess > actual_price else "Too low!"
                if abs(guess - actual_price) > actual_price:
                    feedback += " (More than 2x different!)"

                if self.guesses_remaining > 0:
                    self.result_label.text = f"{feedback} Try again!"
                else:
                    self.result_label.text = (
                        f"Game over! The actual price was £{actual_price:,.0f}"
                    )
                    if not self.properties:
                        Clock.schedule_once(lambda dt: self.return_to_menu(), 2)

        except ValueError:
            self.result_label.text = "Please enter a valid number"

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        if not self.current_property:
            return True

        if keycode[1] == "left":
            self.change_image("left")
        elif keycode[1] == "right":
            self.change_image("right")
        return True

    def _on_keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_key_down)
        self._keyboard = None
