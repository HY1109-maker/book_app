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

def build_query_with_nominatim(query_str, bbox):
    """Nominatimで検索語を解析し、Overpassクエリを構築する"""

    # 1. Nominatimに問い合わせて、検索語からOSMタグを取得
    params = {
        'q': query_str,
        'format': 'json',
        'limit': 1, # 最も関連性の高い結果を1つだけ取得
        'osm_type': 'node,way,relation'
    }
    
    headers = {'Accept-Language': 'ja'} # 結果を日本語優先にする
    api_url = app.config['NOMINATIM_API_URL']
    
    try:
        # Nominatim APIは利用ポリシーがあるため、適切なUser-Agentを設定することが推奨されます
        # headers['User-Agent'] = 'MyAwesomeFoodieApp/1.0 (myemail@example.com)'
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status() # エラーがあれば例外を発生
        results = response.json()
    except requests.RequestException as e:
        print(f"Nominatim API error: {e}")
        # Nominatimが失敗した場合は、単純なname検索にフォールバックする
        return f"""
            [out:json];
            (
              node["name"~"{query_str}"]({bbox});
              way["name"~"{query_str}"]({bbox});
            );
            out center;
        """

    tag_filters = ""
    # Nominatimがカテゴリ情報(class, type)を返した場合、それをタグに変換
    if results and 'class' in results[0] and 'type' in results[0]:
        osm_class = results[0]['class']
        osm_type = results[0]['type']
        
        # Nominatimの分類をOSMの主要なキーにマッピング
        # この部分は必要に応じて拡張できます
        if osm_class in ['amenity', 'shop', 'tourism', 'leisure']:
            tag_filters += f'["{osm_class}"="{osm_type}"]'
        
        # 「フレンチレストラン」のような検索のために、元のクエリもname検索に加える
        tag_filters += f'["name"~"{query_str}",i]'

    else:
        # カテゴリが取れなかった場合は、単純な名称での部分一致検索にする (iは大小文字無視)
        tag_filters = f'["name"~"{query_str}",i]'


    return f"""
        [out:json];
        (
          node{tag_filters}({bbox});
          way{tag_filters}({bbox});
        );
        out center;
    """

# ▼▼▼ 既存のsearch_shops関数を以下のように書き換える ▼▼▼
@app.route('/search_shops')
def search_shops():
    query_str = request.args.get('keyword', 'レストラン')
    bbox = request.args.get('bbox')

    if not bbox:
        return jsonify({"error": "BBox (bounding box) is required"}), 400

    # Nominatimを使う新しい関数でクエリを構築
    overpass_query = build_query_with_nominatim(query_str, bbox)
    
    api_url = app.config['OVERPASS_API_URL']
    response = requests.get(api_url, params={'data': overpass_query})
    
    if response.status_code == 200:
        data = response.json()
        geojson = to_geojson(data)
        return jsonify(geojson)
    else:
        return jsonify({
            "error": "Failed to fetch data from Overpass API",
            "query": overpass_query
        }), 500
