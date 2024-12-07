import json
import random
from typing import List, TypedDict
from urllib.parse import urlencode
import jmespath
from httpx import AsyncClient
import os
import aiofiles
import asyncio
from datetime import datetime
from pathlib import Path
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
    "wolverhampton"
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

def extract_property(response_text: str) -> dict:
    """Extract property data from rightmove PAGE_MODEL javascript variable"""
    from parsel import Selector
    selector = Selector(response_text)
    data = selector.xpath("//script[contains(.,'PAGE_MODEL = ')]/text()").get()
    if not data:
        print("Not a property listing page")
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
            price_sqft = float(results['price_sqft'].replace('£', '').replace(',', ''))
            price_sqmeter = price_sqft * 10.764
            results['price_sqmeter'] = f"£{price_sqmeter:,.2f}"
        except (ValueError, AttributeError):
            results['price_sqmeter'] = None
    else:
        results['price_sqmeter'] = None

    results.pop('price_sqft', None)
    return results

async def fetch_url(url: str, binary: bool = False) -> str:
    """Fetch URL using httpx"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    async with AsyncClient() as client:
        response = await client.get(url, headers=headers, follow_redirects=True)
        if binary:
            return response.content
        return response.text

async def find_locations(query: str) -> List[str]:
    """Use rightmove's typeahead api to find location IDs"""
    tokenize_query = "".join(c + ("/" if i % 2 == 0 else "") for i, c in enumerate(query.upper(), start=1))
    url = f"https://www.rightmove.co.uk/typeAhead/uknostreet/{tokenize_query.strip('/')}/"
    response = await fetch_url(url)
    data = json.loads(response)
    return [prediction["locationIdentifier"] for prediction in data["typeAheadLocations"]]

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
    total_results = int(first_page_data['resultCount'].replace(',', ''))
    results = first_page_data['properties']
    
    max_api_results = 1000
    tasks = []
    for offset in range(RESULTS_PER_PAGE, min(total_results, max_api_results), RESULTS_PER_PAGE):
        tasks.append(fetch_url(make_url(offset)))
    
    if tasks:
        responses = await asyncio.gather(*tasks)
        for response in responses:
            data = json.loads(response)
            results.extend(data['properties'])
    
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

async def download_image(url: str, path: str) -> bool:
    """Download an image from URL and save it to path"""
    try:
        image_data = await fetch_url(url, binary=True)
        async with aiofiles.open(path, 'wb') as f:
            await f.write(image_data)
        return True
    except Exception as e:
        print(f"Error downloading image {url}: {str(e)}")
        return False

async def save_property_data(property_data: dict, base_dir: str) -> Path:
    """Save property data and images to disk"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    property_dir = Path(base_dir) / f"{property_data['id']}_{timestamp}"
    property_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON data
    json_path = property_dir / "property_data.json"
    async with aiofiles.open(json_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(property_data, indent=2, ensure_ascii=False))

    # Create images directory
    images_dir = property_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Download images
    tasks = []
    for i, photo in enumerate(property_data.get('photos', [])):
        if photo and photo.get('url'):
            filename = f"photo_{i}.jpg"
            path = images_dir / filename
            tasks.append(download_image(photo['url'], str(path)))
    
    if tasks:
        await asyncio.gather(*tasks)
    
    return property_dir

async def generate_random_properties(num_properties: int = 1, db: PropertyDatabase = None, progress_callback=None) -> List[dict]:
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
                        property_dir = await save_property_data(property_data, "rightmove_data")
                        db.add_property(property_data, str(property_dir))
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
