import asyncio
import json
import random
from typing import List, TypedDict
from urllib.parse import urlencode
import jmespath
from httpx import AsyncClient, Response
from parsel import Selector
import os
import aiofiles
import aiohttp
from datetime import datetime
from pathlib import Path


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
    "wolverhampton"
]

# HTTP Client setup
client = AsyncClient(
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,lt;q=0.8,et;q=0.7,de;q=0.6",
    },
    follow_redirects=True,
    http2=True,
    timeout=30,
)

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

def extract_property(response: Response) -> dict:
    """Extract property data from rightmove PAGE_MODEL javascript variable"""
    selector = Selector(response.text)
    data = selector.xpath("//script[contains(.,'PAGE_MODEL = ')]/text()").get()
    if not data:
        print(f"page {response.url} is not a property listing page")
        return
    json_data = list(find_json_objects(data))[0]
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
    if results.get('price_sqft'):
        try:
            # Remove '£' and ',' from the string and convert to float
            price_sqft = float(results['price_sqft'].replace('£', '').replace(',', ''))
            # Convert to price per square meter (1 sq meter = 10.764 sq ft)
            price_sqmeter = price_sqft * 10.764
            # Format back to currency string
            results['price_sqmeter'] = f"£{price_sqmeter:,.2f}"
        except (ValueError, AttributeError):
            results['price_sqmeter'] = None
    else:
        results['price_sqmeter'] = None

    # Remove the original price_sqft from results
    results.pop('price_sqft', None)
    
    return results

async def scrape_properties(urls: List[str]) -> List[dict]:
    """Scrape Rightmove property listings for property data"""
    to_scrape = [client.get(url) for url in urls]
    properties = []
    for response in asyncio.as_completed(to_scrape):
        response = await response
        property_data = extract_property(response)
        if property_data:
            properties.append(parse_property(property_data))
    return properties

async def find_locations(query: str) -> List[str]:
    """Use rightmove's typeahead api to find location IDs"""
    tokenize_query = "".join(c + ("/" if i % 2 == 0 else "") for i, c in enumerate(query.upper(), start=1))
    url = f"https://www.rightmove.co.uk/typeAhead/uknostreet/{tokenize_query.strip('/')}/"
    response = await client.get(url)
    data = json.loads(response.text)
    return [prediction["locationIdentifier"] for prediction in data["typeAheadLocations"]]

async def scrape_search(location_id: str) -> dict:
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

    first_page = await client.get(make_url(0))
    first_page_data = json.loads(first_page.content)
    total_results = int(first_page_data['resultCount'].replace(',', ''))
    results = first_page_data['properties']
    
    other_pages = []
    max_api_results = 1000
    for offset in range(RESULTS_PER_PAGE, total_results, RESULTS_PER_PAGE):
        if offset >= max_api_results:
            break
        other_pages.append(client.get(make_url(offset)))
    
    for response in asyncio.as_completed(other_pages):
        response = await response
        data = json.loads(response.text)
        results.extend(data['properties'])
    return results

async def download_image(session: aiohttp.ClientSession, url: str, path: str):
    """Download an image from URL and save it to path"""
    async with session.get(url) as response:
        if response.status == 200:
            async with aiofiles.open(path, mode='wb') as f:
                await f.write(await response.read())
        else:
            print(f"Failed to download {url}: {response.status}")

async def save_property_data(property_data: dict, base_dir: str):
    """Save property data and images to directory"""
    # Create directory using property ID and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    property_dir = Path(base_dir) / f"{property_data['id']}_{timestamp}"
    property_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON data with proper encoding
    json_path = property_dir / "property_data.json"
    async with aiofiles.open(json_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(property_data, indent=2, ensure_ascii=False))
    # Create images directory
    images_dir = property_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Download images
    async with aiohttp.ClientSession() as session:
        # Download property photos
        photo_tasks = []
        for i, photo in enumerate(property_data.get('photos', [])):
            if photo and photo.get('url'):
                filename = f"photo_{i}.png"
                path = images_dir / filename
                photo_tasks.append(download_image(session, photo['url'], str(path)))

        # Download floorplans
        for i, floorplan in enumerate(property_data.get('floorplans', [])):
            if floorplan and floorplan.get('url'):
                filename = f"floorplan_{i}.png"
                path = images_dir / filename
                photo_tasks.append(download_image(session, floorplan['url'], str(path)))

        await asyncio.gather(*photo_tasks)

async def generate_random_properties(num_properties: int = 10) -> List[dict]:
    """Generate random properties from top UK cities"""
    # Select random cities
    selected_cities = random.sample(TOP_UK_CITIES, num_properties)
    properties = []
    
    # Get location IDs for each city
    for city in selected_cities:
        try:
            location_ids = await find_locations(city)
            if location_ids:
                # Get search results for the city
                search_results = await scrape_search(location_ids[0])
                if search_results:
                    # Select a random property from the results
                    random_property = random.choice(search_results)
                    property_url = f"https://www.rightmove.co.uk/properties/{random_property['id']}#/"
                    # Scrape the full property details
                    property_details = await scrape_properties([property_url])
                    if property_details:
                        properties.append(property_details[0])
                        # Save the property data
                        await save_property_data(property_details[0], "rightmove_data")
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")
            continue
            
    return properties

async def main():
    # Create output directory
    output_dir = Path("rightmove_data")
    output_dir.mkdir(exist_ok=True)

    # Generate 10 random properties from top UK cities
    properties = await generate_random_properties(10)
    return properties
            
if __name__ == "__main__":
    asyncio.run(main())
