import json
import urllib.request

def download_and_examine():
    url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/topo_lad.json"
    print("Downloading UK TopoJSON file...")
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    
    # Print the structure
    print("\nTop level keys:", list(data.keys()))
    if 'objects' in data:
        print("\nObject keys:", list(data['objects'].keys()))
        first_key = list(data['objects'].keys())[0]
        print(f"\nFirst geometry in {first_key}:", json.dumps(data['objects'][first_key]['geometries'][0], indent=2))
    if 'arcs' in data:
        print("\nFirst arc:", data['arcs'][0] if data['arcs'] else None)

if __name__ == "__main__":
    download_and_examine()
