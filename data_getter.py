import asyncio
import io
import json
import random
from datetime import datetime
from typing import List, TypedDict
from urllib.parse import urlencode

import jmespath
import matplotlib.pyplot as plt
from httpx import AsyncClient
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon

from database import PropertyDatabase


# Type definitions
class PropertyResult(TypedDict):
    id: str
    available: bool
    archived: bool
    phone: str
    bedrooms: int
    bathrooms: int
    type: str
    property_type: str
    tags: list
    description: str
    title: str
    subtitle: str
    price: str
    price_sqmeter: str
    address: dict
    latitude: float
    longitude: float
    features: list
    history: dict
    photos: list
    floorplans: list
    agency: dict
    industryAffiliations: list
    nearest_airports: list
    nearest_stations: list
    sizings: list
    brochures: list


# Top 20 UK Cities by population
TOP_UK_CITIES = [
    "london",
    "birmingham",
    "glasgow",
    "liverpool",
    "leeds",
    "sheffield",
    "manchester",
    "edinburgh",
    "bristol",
    "cardiff",
    "leicester",
    "coventry",
    "nottingham",
    "newcastle upon tyne",
    "belfast",
    "brighton",
    "hull",
    "plymouth",
    "bradford",
    "wolverhampton",
]


def find_json_objects(text: str, decoder=json.JSONDecoder()):
    """Find JSON objects in text, and generate decoded JSON data"""
    pos = 0
    while True:
        match = text.find("{", pos)
        if match == -1:
            break
        try:
            result, index = decoder.raw_decode(text[match:])
            yield result
            pos = match + index
        except ValueError:
            pos = match + 1


import json
import re

from bs4 import BeautifulSoup


def find_json_objects(text):
    """Find JSON objects in text using regex"""
    pos = 0
    while True:
        match = re.search(r"{", text[pos:])
        if not match:
            return

        start = pos + match.start()
        stack = 1
        pos = start + 1

        for i, char in enumerate(text[pos:], pos):
            if char == "{":
                stack += 1
            elif char == "}":
                stack -= 1
                if stack == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        yield obj
                        pos = i + 1
                        break
                    except json.JSONDecodeError:
                        pos = i + 1
                        break
        else:
            return


def extract_property(response_text: str) -> dict:
    """Extract property data from rightmove PAGE_MODEL javascript variable"""
    soup = BeautifulSoup(response_text, "html.parser")

    # Find script tag containing PAGE_MODEL
    script = soup.find("script", string=re.compile("PAGE_MODEL = "))

    if not script:
        print("Not a property listing page")
        return

    # Extract JSON data
    json_data = list(find_json_objects(script.string))[0]
    return json_data["propertyData"]


def parse_property(data) -> PropertyResult:
    """Parse rightmove cache data for property information"""
    parse_map = {
        "id": "id",
        "available": "status.published",
        "archived": "status.archived",
        "phone": "contactInfo.telephoneNumbers.localNumber",
        "bedrooms": "bedrooms",
        "bathrooms": "bathrooms",
        "type": "transactionType",
        "property_type": "propertySubType",
        "tags": "tags",
        "description": "text.description",
        "title": "text.pageTitle",
        "subtitle": "text.propertyPhrase",
        "price": "prices.primaryPrice",
        "price_sqft": "prices.pricePerSqFt",
        "address": "address",
        "latitude": "location.latitude",
        "longitude": "location.longitude",
        "features": "keyFeatures",
        "history": "listingHistory",
        "photos": "images[*].{url: url, caption: caption}",
        "floorplans": "floorplans[*].{url: url, caption: caption}",
        "agency": """customer.{
            id: branchId,
            branch: branchName,
            company: companyName,
            address: displayAddress,
            commercial: commercial,
            buildToRent: buildToRent,
            isNew: isNewHomeDeveloper
        }""",
        "industryAffiliations": "industryAffiliations[*].name",
        "nearest_airports": "nearestAirports[*].{name: name, distance: distance}",
        "nearest_stations": "nearestStations[*].{name: name, distance: distance}",
        "sizings": "sizings[*].{unit: unit, min: minimumSize, max: maximumSize}",
        "brochures": "brochures",
    }
    results = {}
    for key, path in parse_map.items():
        value = jmespath.search(path, data)
        results[key] = value

    # Convert price per square foot to price per square meter
    if results.get("price_sqft"):
        try:
            price_sqft = float(results["price_sqft"].replace("£", "").replace(",", ""))
            price_sqmeter = price_sqft * 10.764
            results["price_sqmeter"] = f"£{price_sqmeter:,.2f}"
        except (ValueError, AttributeError):
            results["price_sqmeter"] = None
    else:
        results["price_sqmeter"] = None

    results.pop("price_sqft", None)
    return results


async def fetch_url(url: str, binary: bool = False) -> str:
    """Fetch URL using httpx"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    async with AsyncClient() as client:
        response = await client.get(url, headers=headers, follow_redirects=True)
        if binary:
            return response.content
        return response.text


async def find_locations(query: str) -> List[str]:
    """Use rightmove's typeahead api to find location IDs"""
    tokenize_query = "".join(
        c + ("/" if i % 2 == 0 else "") for i, c in enumerate(query.upper(), start=1)
    )
    url = (
        f"https://www.rightmove.co.uk/typeAhead/uknostreet/{tokenize_query.strip('/')}/"
    )
    response = await fetch_url(url)
    data = json.loads(response)
    return [
        prediction["locationIdentifier"] for prediction in data["typeAheadLocations"]
    ]


async def scrape_search(location_id: str) -> List[dict]:
    """Scrape property listings for a given location"""
    RESULTS_PER_PAGE = 24

    def make_url(offset: int) -> str:
        url = "https://www.rightmove.co.uk/api/_search?"
        params = {
            "areaSizeUnit": "sqft",
            "channel": "BUY",
            "currencyCode": "GBP",
            "includeSSTC": "false",
            "index": offset,
            "isFetching": "false",
            "locationIdentifier": location_id,
            "numberOfPropertiesPerPage": RESULTS_PER_PAGE,
            "radius": "0.0",
            "sortType": "6",
            "viewType": "LIST",
        }
        return url + urlencode(params)

    first_page = await fetch_url(make_url(0))
    first_page_data = json.loads(first_page)
    total_results = int(first_page_data["resultCount"].replace(",", ""))
    results = first_page_data["properties"]

    max_api_results = 1000
    tasks = []
    for offset in range(
        RESULTS_PER_PAGE, min(total_results, max_api_results), RESULTS_PER_PAGE
    ):
        tasks.append(fetch_url(make_url(offset)))

    if tasks:
        responses = await asyncio.gather(*tasks)
        for response in responses:
            data = json.loads(response)
            results.extend(data["properties"])

    return results


async def scrape_properties(urls: List[str]) -> List[dict]:
    """Scrape Rightmove property listings for property data"""
    properties = []
    tasks = [fetch_url(url) for url in urls]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for url, response in zip(urls, responses):
        if isinstance(response, Exception):
            print(f"Error scraping {url}: {str(response)}")
            continue
        try:
            property_data = extract_property(response)
            if property_data:
                properties.append(parse_property(property_data))
        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")

    return properties


async def download_image(url: str) -> bytes:
    """Download an image from URL and return the binary data"""
    try:
        return await fetch_url(url, binary=True)
    except Exception as e:
        print(f"Error downloading image {url}: {str(e)}")
        return None


def create_uk_plot(latitude: float, longitude: float) -> bytes:
    """Create a UK map plot with the property location marked"""
    import matplotlib

    matplotlib.use("Agg")  # Set backend before importing pyplot

    # Load the pre-generated UK polygons
    try:
        with open("uk_polygons.json", "r") as f:
            uk_data = json.load(f)
    except FileNotFoundError:
        print("UK polygons file not found. Please run generate_uk_polygons.py first.")
        return None

    fig, ax = plt.subplots(figsize=(10, 12))

    # Create polygon patches
    patches = []
    for polygon_coords in uk_data["polygons"]:
        patches.append(Polygon(polygon_coords, closed=True))

    # Add polygons to plot
    collection = PatchCollection(
        patches, facecolor="lightgray", edgecolor="black", linewidth=0.5
    )
    ax.add_collection(collection)

    # Plot the property location
    ax.plot(longitude, latitude, "ro", markersize=10)

    # Set the plot bounds
    ax.set_xlim(uk_data["bounds"]["x"])
    ax.set_ylim(uk_data["bounds"]["y"])

    plt.title("Position on UK Map")
    plt.axis("off")
    fig.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


async def save_property_data(property_data: dict, db: PropertyDatabase) -> None:
    """Save property data and images to database"""
    # Download images
    images = []
    tasks = []
    for photo in property_data.get("photos", []):
        if photo and photo.get("url"):
            tasks.append(download_image(photo["url"]))

    if tasks:
        image_data = await asyncio.gather(*tasks)
        images = [img for img in image_data if img is not None]

    # Create UK position plot
    plot_data = None
    if property_data.get("latitude") and property_data.get("longitude"):
        plot_data = create_uk_plot(
            property_data["latitude"], property_data["longitude"]
        )

    # Save to database
    db.add_property(property_data, images, plot_data)


async def generate_random_properties(
    num_properties: int = 1, db: PropertyDatabase = None, progress_callback=None
) -> List[dict]:
    """Generate random properties with progress updates"""
    if db is None:
        db = PropertyDatabase()

    selected_cities = random.sample(TOP_UK_CITIES, num_properties)
    properties = []

    for i, city in enumerate(selected_cities):
        try:
            if progress_callback:
                progress_callback(i * 10)  # Update progress (0-100)

            location_ids = await find_locations(city)
            if location_ids:
                search_results = await scrape_search(location_ids[0])
                if search_results:
                    random_property = random.choice(search_results)
                    property_url = f"https://www.rightmove.co.uk/properties/{random_property['id']}#/"
                    property_details = await scrape_properties([property_url])
                    if property_details:
                        property_data = property_details[0]
                        await save_property_data(property_data, db)
                        properties.append(property_data)

                        if progress_callback:
                            progress_callback((i + 1) * 10)  # Update progress (0-100)
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")
            continue

    return properties


if __name__ == "__main__":
    db = PropertyDatabase()
    asyncio.run(generate_random_properties(10, db))
