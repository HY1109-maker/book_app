from app import app # appをインポート
from flask import render_template, request, jsonify, redirect, flash, url_for
import requests 
from app.forms import LoginForm, RegistrationForm,PostForm
from app import db
from app.models import User, Shop, Post
from flask_login import current_user, login_user, logout_user 
import os
import uuid
from werkzeug.utils import secure_filename
from flask_login import login_required
from datetime import datetime, timedelta, timezone
from math import radians, cos, sin, asin, sqrt

@app.route('/')
@app.route('/index')
def index():
    # from DB, all post data is obtained with time order
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', title='Home', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 既にログイン済みの場合は、ホームページにリダイレクト
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # フォームから入力されたusernameでユーザーをデータベースから検索
        user = User.query.filter_by(username=form.username.data).first()
        
        # ユーザーが存在しない、またはパスワードが間違っている場合
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        
        # ログインさせる
        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.username}!')
        return redirect(url_for('index')) # ログイン後はホームページへ
        
    return render_template('login_page.html', title='Sign In', form=form)


# ▼▼▼ ログアウト用のルートを末尾に追加 ▼▼▼
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/map_page')
def map_page():
    return render_template('map.html', title='Map')


def to_geojson(overpass_json):
    """Overpass APIのJSONをGeoJSON FeatureCollection形式に変換するヘルパー関数"""
    features = []
    for element in overpass_json.get('elements', []):
        properties = element.get('tags', {})

        properties['osm_id'] = element.get('id')

        
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

@app.route('/api/osm_search')
def osm_search():
    query_str = request.args.get('keyword', 'restaurant')
    bbox = request.args.get('bbox')

    if not bbox:
        return jsonify({"error": "BBox is required"}), 400

    # 以前作成したNominatim連携のクエリビルダーを再利用
    overpass_query = build_query_with_nominatim(query_str, bbox)
    
    api_url = app.config['OVERPASS_API_URL']
    response = requests.get(api_url, params={'data': overpass_query})
    
    if response.status_code == 200:
        data = response.json()
        geojson = to_geojson(data) # to_geojsonでGeoJSONに変換
        return jsonify(geojson)
    else:
        return jsonify({"error": "Failed to fetch data from Overpass API"}), 500



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

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


# ... (既存のインポート) ...

# ▼▼▼ 既存の create_post 関数を、以下のように全体を書き換える ▼▼▼
@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        # --- 1. 画像の保存処理 (変更なし) ---
        image_file = form.image.data
        filename = secure_filename(image_file.filename)
        unique_filename = str(uuid.uuid4()) + "_" + filename
        upload_path = os.path.join(app.root_path, 'static/uploads', unique_filename)
        image_file.save(upload_path)

        # --- 2. Nominatim APIでお店の情報を検索 ---
        shop_name_query = form.shop_name.data
        
        # Nominatim APIのエンドポイント (config.pyから読み込むのが望ましい)
        nominatim_url = 'https://nominatim.openstreetmap.org/search'
        params = {
            'q': shop_name_query,
            'format': 'json',
            'limit': 1, # 最も関連性の高い結果を1つだけ取得
            'countrycodes': 'jp' # 日本国内に限定
        }
        headers = {'Accept-Language': 'ja',
                   'User-Agent': 'FoodiesFanApp/1.0 (https://your-app-url.com or your-email@example.com)'
        }
        
        try:
            response = requests.get(nominatim_url, params=params, headers=headers)
            # 200 OK以外のステータスコードが返ってきた場合にエラーを発生させる
            response.raise_for_status() 
            shop_data = response.json()
        except (requests.RequestException, ValueError) as e:
            # ネットワークエラーやJSONデコードエラーをキャッチ
            flash(f'Could not retrieve shop information. Error: {e}')
            return redirect(url_for('create_post'))

        if not shop_data:
            flash('Shop not found. Please try a more specific name.')
            return redirect(url_for('create_post'))

       
         # --- ▼▼▼ お店の情報をフォームの隠しフィールドから取得するように変更 ▼▼▼ ---
        osm_id = form.shop_osm_id.data
        shop_name = form.shop_name.data
        latitude = form.shop_latitude.data
        longitude = form.shop_longitude.data

        # --- データベースでお店の情報を検索または作成 ---
        shop = Shop.query.filter_by(osm_id=osm_id).first()
        if not shop:
            shop = Shop(
                osm_id=osm_id,
                name=shop_name,
                latitude=float(latitude),
                longitude=float(longitude)
            )
            db.session.add(shop)
        
        # --- 投稿をデータベースに保存 (変更なし) ---
        post = Post(
            image_filename=unique_filename,
            body=form.comment.data,
            author=current_user,
            shop=shop
        )
        db.session.add(post)
        db.session.commit()
        
        flash('Your post is now live!')
        return redirect(url_for('index'))

    return render_template('create_post.html', title='New Post', form=form)


@app.route('/api/shops')
def get_shops():
    """データベースに保存されている全てのお店の情報をGeoJSON形式で返す"""
    shops = Shop.query.all()
    features = []
    for shop in shops:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [shop.longitude, shop.latitude]
            },
            "properties": {
                "id": shop.id,
                "name": shop.name,
                "osm_id": shop.osm_id
            }
        })
    
    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })

@app.route('/api/shops/<int:shop_id>/posts')
def get_posts_for_shop(shop_id):
    """指定されたお店IDに関連する投稿を返す"""
    shop = Shop.query.get_or_404(shop_id)
    posts_data = []
    # 新しい投稿が先に表示されるように並び替え
    for post in shop.posts.order_by(Post.timestamp.desc()):
        posts_data.append({
            'id': post.id,
            'body': post.body,
            'image_filename': post.image_filename,
            'author_username': post.author.username
        })
    return jsonify(posts_data)


# @app.route('/timeline')
# @login_required # タイムラインはログインしているユーザーのみが見れるようにします
# def timeline():
#     # データベースから全ての投稿を新しい順に取得
#     posts = Post.query.order_by(Post.timestamp.desc()).all()
#     return render_template('timeline.html', title='Timeline', posts=posts)


# ▼▼▼ 2点間の距離を計算するヘルパー関数（ハーベサイン公式）を追加 ▼▼▼
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees)
    """
    # 緯度経度をラジアンに変換
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # ハーベサインの公式
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # 地球の半径 (km)
    return c * r

# ▼▼▼ /timelineルートをAPIに変更し、/api/timelineとして作成 ▼▼▼
@app.route('/api/timeline')
@login_required
def api_timeline():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    recent_date = datetime.now(timezone.utc) - timedelta(days=30)
    base_query = Post.query.filter(Post.timestamp >= recent_date)

    if lat is not None and lon is not None:
        posts = base_query.all()
        scored_posts = []
        
        for post in posts:
            # ▼▼▼ このif文を追加 ▼▼▼
            # shopと、その緯度経度がNoneでないことを確認する
            if post.shop and post.shop.latitude is not None and post.shop.longitude is not None:
                # --- 2. 距離スコアの計算 ---
                distance = haversine(lon, lat, post.shop.longitude, post.shop.latitude)
                distance_score = 1 / (distance + 1)

                # --- 3. 時間スコアの計算 ---
                now = datetime.now(timezone.utc)
                #  ▼▼▼ post.timestampにタイムゾーン情報を付与して比較 ▼▼▼
                post_time_aware = post.timestamp.replace(tzinfo=timezone.utc)
                hours_ago = (now - post_time_aware).total_seconds() / 3600
                time_score = 1 / (hours_ago + 1)

                # --- 4. 最終スコアの計算 (重み付け) ---
                final_score = (time_score * 0.6) + (distance_score * 0.4)
                
                scored_posts.append({'post': post, 'score': final_score})
            # ▲▲▲ ここまで ▲▲▲
        
        # スコアが高い順にソート
        sorted_posts_list = sorted(scored_posts, key=lambda x: x['score'], reverse=True)
        posts = [item['post'] for item in sorted_posts_list]
    else:
        # 緯度経度がなければ、通常通り新しい順にソート
        posts = base_query.order_by(Post.timestamp.desc()).all()

    # JSONレスポンスを生成 (変更なし)
    posts_data = [{
        'id': post.id,
        'body': post.body,
        'image_filename': post.image_filename,
        'author_username': post.author.username,
        'shop_name': post.shop.name
    } for post in posts]
    
    return jsonify(posts_data)


# ▼▼▼ 既存の /timeline ルートは、HTMLを返すだけのシンプルなものにする ▼▼▼
@app.route('/timeline')
@login_required
def timeline():
    # このルートはtimeline.htmlをレンダリングするだけ
    # 実際のデータは上記のJavaScriptが/api/timelineから取得する
    return render_template('timeline.html', title='Timeline')
