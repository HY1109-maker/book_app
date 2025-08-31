from app import app # appをインポート
from flask import render_template, request, jsonify 
import requests 
from app.forms import LoginForm

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/login')
def login():
    form = LoginForm()
    return render_template('login_page.html', title='Login', form=form)

@app.route('/map')
def map():
    return render_template('map.html', title='Map')


def to_geojson(overpass_json):
    """Overpass APIのJSONをGeoJSON FeatureCollection形式に変換するヘルパー関数"""
    features = []
    for element in overpass_json.get('elements', []):
        properties = element.get('tags', {})
        
        if element['type'] == 'node':
            geometry = {
                "type": "Point",
                "coordinates": [element.get('lon'), element.get('lat')]
            }
        elif element['type'] == 'way' and 'center' in element:
            geometry = {
                "type": "Point",
                "coordinates": [element['center'].get('lon'), element['center'].get('lat')]
            }
        else:
            continue

        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.route('/search_shops')
def search_shops():
    keyword = request.args.get('keyword', 'restaurant')
    bbox = request.args.get('bbox')

    if not bbox:
        return jsonify({"error": "BBox (bounding box) is required"}), 400

    overpass_query = f"""
        [out:json];
        (
          node["amenity"="{keyword}"]({bbox});
          way["amenity"="{keyword}"]({bbox});
        );
        out center;
    """

    api_url = app.config['OVERPASS_API_URL']
    response = requests.get(api_url, params={'data': overpass_query})
        
    if response.status_code == 200:
        data = response.json()
        geojson = to_geojson(data)
        return jsonify(geojson)
    else:
        return jsonify({"error": "Failed to fetch data from Overpass API"}), 500