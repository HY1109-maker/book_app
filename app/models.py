from datetime import datetime, timezone
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key = True, nullable=False)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index =True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    posts = db.relationship('Post', back_populates='author', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
    

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)
    image_filename = db.Column(db.String(128), nullable = False) # 画像ファイル名を保存するカラム

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_post_user_id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id', name='fk_post_shop_id'), nullable=False)

    author = db.relationship('User', back_populates='posts')
    shop = db.relationship('Shop', back_populates='posts')


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

    def __repr__(self):
        return f'<Shop {self.name}>'