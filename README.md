# Property Price Game

A interactive game where players guess the prices of real UK properties. Built with Kivy and using real estate data from Rightmove.

## Features

- Interactive property price guessing game
- Real UK property data with images
- UK map visualization showing property locations
- Progressive information reveal system
- Score tracking
- Support for both desktop and iOS platforms
- Property data caching for offline play

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/property-price-game.git
cd property-price-game
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up pre-commit hooks:
```bash
pre-commit install
```

4. Generate UK map data (required for location plotting):
```bash
python generate_uk_polygons.py
```

## Development

This project uses pre-commit hooks to maintain code quality. The following checks are run automatically before each commit:

- black: Code formatting
- isort: Import sorting
- flake8: Style guide enforcement
- mypy: Type checking
- Additional checks for common issues

To run the checks manually:
```bash
pre-commit run --all-files
```

## Usage

1. Run the game:
```bash
python main.py
```

2. On first launch, click "Generate new data" to fetch property data
3. Click "Start" to begin playing
4. For each property:
   - View property images using arrow keys or navigation buttons
   - Enter your price guess
   - Get feedback and additional property information with each guess
   - Score points for accurate guesses within 5% of actual price

## iOS Build

To build for iOS:

1. Ensure you have Xcode installed
2. Run the iOS build script:
```bash
./build_ios.sh
```

## Technical Details

- **Frontend**: Kivy GUI framework
- **Data Storage**: SQLite database
- **Data Source**: Rightmove property listings
- **Visualization**: Matplotlib for UK map plotting
- **Image Processing**: Property images and location maps
- **Async Operations**: Property data fetching and processing
- **Code Quality**: Enforced through pre-commit hooks

## Project Structure

- `main.py`: Application entry point
- `kivy_app.py`: Main game interface and logic
- `data_getter.py`: Property data scraping and processing
- `database.py`: Database operations
- `generate_uk_polygons.py`: UK map data generation
- `build_ios.sh`: iOS build script
- `.pre-commit-config.yaml`: Code quality configuration

## Dependencies

See `requirements.txt` for a complete list of dependencies.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Note

This application is for educational purposes only. Please ensure you comply with Rightmove's terms of service and maintain reasonable request rates when fetching property data.
