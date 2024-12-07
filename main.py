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
from database import PropertyDatabase
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.internet.ssl import ClientContextFactory
from twisted.web.http_headers import Headers
from twisted.web.client import HTTPConnectionPool
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import ProxyAgent

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

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

pool = HTTPConnectionPool(reactor)
agent = Agent(reactor, WebClientContextFactory(), pool=pool)

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

@inlineCallbacks
def fetch_url(url, binary=False):
    """Fetch URL using Twisted's Agent"""
    headers = Headers({
        'User-Agent': ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'],
        'Accept': ['text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'],
        'Accept-Language': ['en-US,en;q=0.5'],
    })
    
    response = yield agent.request(b'GET', url.encode('utf-8'), headers)
    body = yield readBody(response)
    if binary:
        defer.returnValue(body)
    else:
        defer.returnValue(body.decode('utf-8'))

@inlineCallbacks
def find_locations(query: str):
    """Use rightmove's typeahead api to find location IDs"""
    tokenize_query = "".join(c + ("/" if i % 2 == 0 else "") for i, c in enumerate(query.upper(), start=1))
    url = f"https://www.rightmove.co.uk/typeAhead/uknostreet/{tokenize_query.strip('/')}/"
    response = yield fetch_url(url)
    data = json.loads(response)
    defer.returnValue([prediction["locationIdentifier"] for prediction in data["typeAheadLocations"]])

@inlineCallbacks
def scrape_search(location_id: str):
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

    first_page = yield fetch_url(make_url(0))
    first_page_data = json.loads(first_page)
    total_results = int(first_page_data['resultCount'].replace(',', ''))
    results = first_page_data['properties']
    
    max_api_results = 1000
    for offset in range(RESULTS_PER_PAGE, min(total_results, max_api_results), RESULTS_PER_PAGE):
        page_data = yield fetch_url(make_url(offset))
        data = json.loads(page_data)
        results.extend(data['properties'])
    
    defer.returnValue(results)

@inlineCallbacks
def scrape_properties(urls: List[str]):
    """Scrape Rightmove property listings for property data"""
    properties = []
    for url in urls:
        try:
            response = yield fetch_url(url)
            property_data = extract_property(response)
            if property_data:
                properties.append(parse_property(property_data))
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
    defer.returnValue(properties)

@inlineCallbacks
def download_image(url: str, path: str):
    """Download an image from URL and save it to path"""
    try:
        # Get binary image data
        image_data = yield fetch_url(url, binary=True)
        
        # Write binary data directly to file
        with open(path, 'wb') as f:
            f.write(image_data)
            
        defer.returnValue(True)
    except Exception as e:
        print(f"Error downloading image {url}: {str(e)}")
        defer.returnValue(False)

@inlineCallbacks
def save_property_data(property_data: dict, base_dir: str):
    """Save property data and images to disk"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    property_dir = Path(base_dir) / f"{property_data['id']}_{timestamp}"
    property_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON data
    json_path = property_dir / "property_data.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(property_data, f, indent=2, ensure_ascii=False)

    # Create images directory
    images_dir = property_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Download images
    for i, photo in enumerate(property_data.get('photos', [])):
        if photo and photo.get('url'):
            filename = f"photo_{i}.jpg"  # Changed to .jpg since Rightmove uses JPEG
            path = images_dir / filename
            try:
                success = yield download_image(photo['url'], str(path))
                if not success:
                    print(f"Failed to download image {i} for property {property_data['id']}")
            except Exception as e:
                print(f"Error saving image {i} for property {property_data['id']}: {str(e)}")
    
    defer.returnValue(property_dir)

@inlineCallbacks
def generate_random_properties(num_properties: int = 1, db: PropertyDatabase = None):
    """Generate random properties using Twisted's deferred pattern"""
    if db is None:
        db = PropertyDatabase()
    
    selected_cities = random.sample(TOP_UK_CITIES, num_properties)
    properties = []
    
    for city in selected_cities:
        try:
            location_ids = yield find_locations(city)
            if location_ids:
                search_results = yield scrape_search(location_ids[0])
                if search_results:
                    random_property = random.choice(search_results)
                    property_url = f"https://www.rightmove.co.uk/properties/{random_property['id']}#/"
                    property_details = yield scrape_properties([property_url])
                    if property_details:
                        property_data = property_details[0]
                        property_dir = yield save_property_data(property_data, "rightmove_data")
                        db.add_property(property_data, str(property_dir))
                        properties.append(property_data)
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")
            continue
    
    defer.returnValue(properties)

if __name__ == "__main__":
    db = PropertyDatabase()
    d = generate_random_properties(10, db)
    d.addCallback(lambda result: reactor.stop())
    reactor.run()
