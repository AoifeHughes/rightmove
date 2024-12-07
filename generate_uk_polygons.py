import json
import urllib.request

def download_topojson():
    """Download the UK TopoJSON file"""
    url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/topo_lad.json"
    print("Downloading UK TopoJSON file...")
    response = urllib.request.urlopen(url)
    data = response.read()
    return json.loads(data)

def transform_point(point, transform):
    """Transform a point using TopoJSON transform parameters"""
    x = transform['scale'][0] * point[0] + transform['translate'][0]
    y = transform['scale'][1] * point[1] + transform['translate'][1]
    return [x, y]

def decode_arc(arc, transform):
    """Decode a delta-encoded arc to absolute coordinates"""
    points = []
    x, y = 0, 0  # Initialize previous point
    
    for delta in arc:
        # Add delta to previous coordinates (delta encoding)
        x += delta[0]
        y += delta[1]
        # Transform to actual coordinates
        point = transform_point([x, y], transform)
        points.append(point)
    
    return points

def extract_polygon_coordinates(arc_indices, topology_arcs, transform):
    """Extract and transform coordinates for a polygon"""
    coordinates = []
    
    # Handle nested arrays for MultiPolygon
    if isinstance(arc_indices[0], list):
        for ring_indices in arc_indices:
            ring_coords = []
            for idx in ring_indices:
                # Handle negative indices (reversed arc)
                actual_idx = abs(idx) - 1 if idx < 0 else idx
                arc = topology_arcs[actual_idx]
                # Decode and transform the arc
                points = decode_arc(arc, transform)
                if idx < 0:  # If negative, reverse the coordinates
                    points = points[::-1]
                # Extend ring coordinates, excluding duplicate point at ring junction
                if len(ring_coords) > 0:
                    ring_coords.extend(points[1:])
                else:
                    ring_coords.extend(points)
            coordinates.append(ring_coords)
    else:
        # Single ring polygon
        ring_coords = []
        for idx in arc_indices:
            actual_idx = abs(idx) - 1 if idx < 0 else idx
            arc = topology_arcs[actual_idx]
            points = decode_arc(arc, transform)
            if idx < 0:
                points = points[::-1]
            if len(ring_coords) > 0:
                ring_coords.extend(points[1:])
            else:
                ring_coords.extend(points)
        coordinates.append(ring_coords)
    
    return coordinates

def extract_polygons(topojson):
    """Extract polygon coordinates from TopoJSON"""
    polygons = []
    transform = topojson['transform']
    topology_arcs = topojson['arcs']
    
    # Get the geometries from the first object
    first_key = list(topojson['objects'].keys())[0]
    geometries = topojson['objects'][first_key]['geometries']
    
    for geometry in geometries:
        if geometry['type'] == 'Polygon':
            coords = extract_polygon_coordinates(geometry['arcs'], topology_arcs, transform)
            polygons.extend(coords)
        elif geometry['type'] == 'MultiPolygon':
            for poly_arcs in geometry['arcs']:
                coords = extract_polygon_coordinates(poly_arcs, topology_arcs, transform)
                polygons.extend(coords)
    
    return polygons

def save_polygons(polygons, output_file='uk_polygons.json'):
    """Save polygons to JSON file"""
    print(f"Saving {len(polygons)} polygons to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump({
            'polygons': polygons,
            'bounds': {
                'x': [-8, 2],  # UK longitude bounds from original plot
                'y': [50, 59]  # UK latitude bounds from original plot
            }
        }, f)

def main():
    # Download and parse TopoJSON
    topojson = download_topojson()
    
    # Extract polygons
    print("Extracting and transforming polygons...")
    polygons = extract_polygons(topojson)
    
    # Save to file
    save_polygons(polygons)
    
    print("Done! You can now use uk_polygons.json for plotting without shapely/geopandas")

if __name__ == "__main__":
    main()
