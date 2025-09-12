from datetime import datetime, timezone
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

likes = db.Table('likes',
                 db.Column('user_id', db.Integer, db.ForeignKey('user.id', name='fk_likes_user_id')),
                 db.Column('post_id', db.Integer, db.ForeignKey('post.id', name='fk_likes_post_id')))


followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id', name='fk_followers_follower_id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id', name='fk_followers_followed_id'))
)

bookmarks = db.Table('bookmarks',
                    db.Column('user_id', db.Integer, db.ForeignKey('user.id', name='fk_bookmarks_user_id')),
                    db.Column('shop_id', db.Integer, db.ForeignKey('shop.id', name='fk_bookmarks_shop_id')) 
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key = True, nullable=False)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index =True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')

    # bookmarked_shop
    bookmarked_shops = db.relationship('Shop', secondary=bookmarks, back_populates='bookmarked_by', lazy='dynamic')

    def bookmark_shop(self, shop):
        if not self.has_bookmarked_shop(shop):
            self.bookmarked_shops.append(shop)

    def unbookmark_shop(self, shop):
        if self.has_bookmarked_shop(shop):
            self.bookmarked_shops.remove(shop)
        
    def has_bookmarked_shop(self, shop):
        return self.bookmarked_shops.filter(
            bookmarks.c.shop_id == shop.id).count() > 0

    # liked_post
    liked_posts = db.relationship('Post', secondary=likes, back_populates='likers', lazy='dynamic')
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0
    
    def followed_posts(self):
        # フォローしているユーザーの投稿を取得
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                followers.c.follower_id == self.id)
        # 自分の投稿も取得
        own = Post.query.filter_by(user_id=self.id)
        # 2つのクエリを結合して返す
        return followed.union(own)


    # helper methods for making "like function"
    def like_post(self, post):
        if not self.has_liked_post(post):
            self.liked_posts.append(post)

    def unlike_post(self, post):
        if self.has_liked_post(post):
            self.liked_posts.remove(post)

    def has_liked_post(self, post):
        return self.liked_posts.filter(likes.c.post_id == post.id).count() > 0
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
    

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)
    image_filename = db.Column(db.String(128), nullable = False) # 画像ファイル名を保存するカラム

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_post_user_id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id', name='fk_post_shop_id'), nullable=False)

    author = db.relationship('User', back_populates='posts')
    shop = db.relationship('Shop', back_populates='posts')

    # likers
    likers = db.relationship('User', secondary=likes, back_populates='liked_posts', lazy='dynamic', cascade="all, delete")
    comments = db.relationship('Comment', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')


    def __repr__(self):
        return f'<Post {self.body}>'

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # save OSM_ID to prevent from dual registration
    osm_id = db.Column(db.BigInteger, index=True, unique=True, nullable = False)
    name = db.Column(db.String(128), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


    # make relation with posts
    posts = db.relationship('Post', back_populates='shop', lazy='dynamic')

    # with bookmarks
    bookmarked_by = db.relationship('User', secondary = bookmarks, back_populates='bookmarked_shops', lazy='dynamic')

    def __repr__(self):
        return f'<Shop {self.name}>'
    

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_comment_user_id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', name='fk_comment_user_id'), nullable=False)

    author = db.relationship('User', back_populates='comments')
    post = db.relationship('Post', back_populates='comments')

    def __repr__(self):
        return f'<Comment {self.body}>'