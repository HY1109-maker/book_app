from app import app # appをインポート
from flask import render_template, request, jsonify, redirect, flash, url_for
import requests 
from app.forms import LoginForm, RegistrationForm
from app import db
from app.models import User
from flask_login import current_user, login_user, logout_user 
import os
import uuid
from werkzeug.utils import secure_filename
from flask_login import login_required
from app.forms import PostForm
from app.models import Shop, Post

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


@app.route('/create_post', methods = ['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        # 1.save img
        image_file = form.image.data
        # change filename as secured name
        filename = secure_filename(image_file.filename)
        unique_filename = str(uuid.uuid4()) + "_" + filename
        # save path
        upload_path = os.path.join(app.root_path, 'static/uploads', unique_filename)
        # saving
        image_file.save(upload_path)

        # 2. searching restaurants or making new it
        shop_name = form.shop_name.data
        # Here, saving restaurants info into DB, the info is from Nomination API, now its damydata
        shop = Shop.query.filter_by(name=shop_name).first()
        if not shop:
            # In actual case, latitudes are required with API 
            shop = Shop(osm_id = int(uuid.uuid4().int % 100000), name = shop_name, latitude = 35.0, longitude = 135.7)
            db.session.add(shop)
            db.session.commit() 

        # 3. saving post with DB
        post = Post(
            image_filename = unique_filename,
            body=form.comment.data,
            author = current_user,
            shop = shop
        )
        db.session.add(post)
        db.session.commit()

        flash('Your post is now live!')
        return redirect(url_for('index')) # 投稿後はトップページへ

    return render_template('create_post.html', title='New Post', form=form)