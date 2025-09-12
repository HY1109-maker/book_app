from app import app # appをインポート
from flask import render_template, request, jsonify, redirect, flash, url_for
import requests 
from app.forms import LoginForm, RegistrationForm,PostForm, CommentForm
from app import db
from app.models import User, Shop, Post, Comment
from flask_login import current_user, login_user, logout_user 
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.exceptions import Forbidden
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


def build_query_based_on_keyword(keyword, bbox):
    """
    キーワードを解析し、カテゴリ検索か名称検索かを判断して
    Overpass APIのクエリを生成する
    """
    # 一般的なカテゴリキーワードと、対応するOSMのタグ
    CATEGORY_KEYWORDS = {
        'カフェ': '["amenity"="cafe"]',
        'レストラン': '["amenity"="restaurant"]',
        'パン': '["shop"="bakery"]',
        '居酒屋': '["amenity"="izakaya"]',
        'バー': '["amenity"="bar"]',
        'ラーメン': '["cuisine"="ramen"]',
        '和食': '["cuisine"="japanese"]',
        'イタリアン': '["cuisine"="italian"]',
        'フレンチ': '["cuisine"="french"]',
        '中華': '["cuisine"="chinese"]',
        '寿司': '["cuisine"="sushi"]',
        'カレー': '["cuisine"="curry"]',
    }
    
    # キーワードがカテゴリ辞書に完全一致するかチェック
    if keyword in CATEGORY_KEYWORDS:
        tag = CATEGORY_KEYWORDS[keyword]
        # カテゴリ検索の場合は、そのタグを持つ施設を検索
        query_part = f"node{tag}({bbox}); way{tag}({bbox});"
    else:
        # カテゴリでない場合は、名称でのあいまい検索
        query_part = f'node["name"~"{keyword}",i]({bbox}); way["name"~"{keyword}",i]({bbox});'
        
    return f"""
        [out:json];
        ({query_part});
        out center;
    """


@app.route('/api/osm_search')
def osm_search():
    keyword = request.args.get('keyword', 'restaurant')
    bbox = request.args.get('bbox')
    if not bbox: return jsonify({"error": "BBox is required"}), 400

    overpass_query = build_query_based_on_keyword(keyword, bbox)
    
    api_url = app.config['OVERPASS_API_URL']
    response = requests.get(api_url, params={'data': overpass_query})
    
    if response.status_code == 200:
        data = response.json()
        geojson = to_geojson(data) # to_geojsonヘルパー関数は必要です
        return jsonify(geojson)
    else:
        return jsonify({"error": "Failed to fetch data from Overpass API"}), 500


@app.route('/search_shops')
def search_shops():
    query_str = request.args.get('keyword', 'レストラン')
    bbox = request.args.get('bbox')

    if not bbox:
        return jsonify({"error": "BBox (bounding box) is required"}), 400

    # Nominatimを使う新しい関数でクエリを構築
    overpass_query = build_query_based_on_keyword(query_str, bbox)
    
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

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

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
                   'User-Agent': 'FoodiesFanApp/1.0 (kuanshangang@gmail.com)'
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
                "osm_id": shop.osm_id,
                "is_bookmarked": current_user.has_bookmarked_shop(shop)
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
            'author_username': post.author.username,
            'comments_count' : post.comments.count()
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


@app.route('/api/timeline')
@login_required
def api_timeline():
    page = request.args.get('page', 1, type=int)
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    filter_mode = request.args.get('filter', 'all')
    POSTS_PER_PAGE = 9

    # 1. まずはDBで30日以内の投稿に絞り込む（パフォーマンスのため）
    recent_date_naive = (datetime.utcnow() - timedelta(days=30))
    base_query = Post.query.filter(Post.timestamp >= recent_date_naive)

    # 2. ページネーションを適用
    if filter_mode == 'following':
        # フォローしているユーザーの投稿だけを取得するクエリ
        base_query = current_user.followed_posts().order_by(Post.timestamp.desc())
    else:
        # これまで通り、全ての投稿を取得するクエリ
        base_query = Post.query.order_by(Post.timestamp.desc())

    pagination = base_query.paginate(
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    posts_on_page = pagination.items
    
    # 3. 緯度経度がある場合、取得した投稿を並び替える
    if lat is not None and lon is not None:
        sortable_posts = []
        for post in posts_on_page:
            distance = float('inf') # デフォルトは無限遠
            if post.shop and post.shop.latitude is not None and post.shop.longitude is not None:
                distance = haversine(lon, lat, post.shop.longitude, post.shop.latitude)

            sortable_posts.append({
                'post': post,
                'timestamp': post.timestamp,
                'distance': distance,
                'likes': post.likers.count()
            })
        
        # 4. 優先順位に従ってソート (1.時間(降順), 2.距離(昇順), 3.いいね(降順))
        # 降順にしたいキーにはマイナスを付ける
        sorted_list = sorted(sortable_posts, key=lambda x: (x['timestamp'], -x['distance'], -x['likes']), reverse=True)
        posts = [item['post'] for item in sorted_list]
    else:
        # 緯度経度がなければ、そのまま表示
        posts = posts_on_page

    # JSONレスポンスを生成
    posts_data = [{
        'id': post.id,
        'body': post.body,
        'image_filename': post.image_filename,
        'author_username': post.author.username,
        'shop_name': post.shop.name,
        'likes_count': post.likers.count(),
        'is_liked_by_user': current_user.has_liked_post(post),
        'comments_count' : post.comments.count()
    } for post in posts]
    
    return jsonify({
        'posts': posts_data,
        'has_next_page': pagination.has_next
    })



# ▼▼▼ 既存の /timeline ルートは、HTMLを返すだけのシンプルなものにする ▼▼▼
@app.route('/timeline')
@login_required
def timeline():
    # このルートはtimeline.htmlをレンダリングするだけ
    # 実際のデータは上記のJavaScriptが/api/timelineから取得する
    return render_template('timeline.html', title='Timeline')


@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like(post_id):
    post = Post.query.get_or_404(post_id)
    current_user.like_post(post)
    db.session.commit()
    return jsonify({'status': 'ok', 'likes_count': post.likers.count()})

@app.route('/unlike/<int:post_id>', methods=['POST'])
@login_required
def unlike(post_id):
    post = Post.query.get_or_404(post_id)
    current_user.unlike_post(post)
    db.session.commit()
    return jsonify({'status': 'ok', 'likes_count': post.likers.count()})

@app.route('/shop/<int:shop_id>')
@login_required
def shop_page(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    posts = shop.posts.order_by(Post.timestamp.desc()).all()
    return render_template('shop_page.html', title=shop.name, shop=shop, posts=posts)


@app.route('/user/<username>')
@login_required
def user_profile(username):
    # URLで指定されたusernameを持つユーザーをデータベースから探す
    # 見つからなかった場合は404エラーを返す
    user = User.query.filter_by(username=username).first_or_404()
    
    # そのユーザーの投稿を新しい順に取得
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    
    return render_template('user_profile.html', title=f"{user.username}'s Profile", user=user, posts=posts)


@app.route('/api/user/<username>/shops')
@login_required
def get_user_shops(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # ユーザーの投稿から、ユニークなお店のリストを取得
    shops = set(post.shop for post in user.posts)
    
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
                "name": shop.name
            }
        })
    
    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'status': 'error', 'message': 'User not found.'}), 404
    if user == current_user:
        return jsonify({'status': 'error', 'message': 'You cannot follow yourself!'}), 400
    current_user.follow(user)
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'message': f'You are now following {username}.',
        'followers_count': user.followers.count()
    })

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'status': 'error', 'message': 'User not found.'}), 404
    if user == current_user:
        return jsonify({'status': 'error', 'message': 'You cannot unfollow yourself!'}), 400
    current_user.unfollow(user)
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'message': f'You have unfollowed {username}.',
        'followers_count': user.followers.count()
    })

@app.route('/user/<username>/followers')
@login_required
def followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    users = user.followers.all()
    return render_template('follow_list.html', title=f'Followers of {user.username}', users=users, user=user)

@app.route('/user/<username>/following')
@login_required
def following(username):
    user = User.query.filter_by(username=username).first_or_404()
    users = user.followed.all()
    return render_template('follow_list.html', title=f'Following by {user.username}', users=users, user=user)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    # フォームが送信され、内容が有効だった場合の処理
    if form.validate_on_submit():
        comment = Comment(
            body=form.comment_body.data,
            post=post,
            author=current_user
        )
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been published.')
        # 投稿後は同じページにリダイレクトして、フォームの再送信を防ぐ
        return redirect(url_for('post_detail', post_id=post.id))
    
    # この投稿に紐づく全てのコメントを新しい順に取得
    comments = post.comments.order_by(Comment.timestamp.desc()).all()
    
    return render_template(
        'post_detail.html', 
        title=f"Post by {post.author.username}", 
        post=post, 
        form=form, 
        comments=comments
    )


@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post_to_delete = Post.query.get_or_404(post_id)
    
    # 投稿の作者が、現在ログインしているユーザーと一致するかをチェック
    if post_to_delete.author != current_user:
        # 一致しない場合は、403 Forbiddenエラーを返す
        raise Forbidden()

    # データベースから投稿を削除
    # (Commentモデルのcascade設定により、関連するコメントも自動で削除されます)
    db.session.delete(post_to_delete)
    
    # アップロードされた画像ファイルもサーバーから削除 (任意ですが推奨)
    try:
        image_path = os.path.join(app.root_path, 'static/uploads', post_to_delete.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        print(f"Error deleting image file: {e}") # エラーログを残す

    db.session.commit()
    flash('Your post has been deleted.')
    # 削除後は、そのユーザーのプロフィールページにリダイレクト
    return redirect(url_for('user_profile', username=current_user.username))

@app.route('/bookmark/<int:shop_id>', methods=['POST'])
@login_required
def bookmark(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    current_user.bookmark_shop(shop)
    db.session.commit()
    return jsonify({'status':'ok', 'message':'Shop bookmarked'})

@app.route('/unbookmark/<int:shop>', methods=['POST'])
@login_required
def unbookmark(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    current_user.unbookmark_shop(shop)
    db.session.commit()
    return jsonify({'status':'ok', 'message':'Shop unbookmarked'})

