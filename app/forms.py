from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, ValidationError, Email, EqualTo, Optional
from app.models import User # --- Userモデルをインポート ---
from flask_wtf.file import FileField, FileRequired, FileAllowed


class LoginForm(FlaskForm):
    username = StringField('ユーザー名', validators=[DataRequired()])
    password = StringField('パスワード', validators=[DataRequired()])
    remember_me = BooleanField('ログインを記録する')
    submit = SubmitField('サインイン')

class RegistrationForm(FlaskForm):
    username = StringField('ユーザー名', validators=[DataRequired()])
    email = StringField('メールアドレス', validators=[DataRequired(), Email()])
    password = PasswordField('パスワード', validators=[DataRequired()])
    password2 = PasswordField(
        '確認用パスワード', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('登録')
    
    # check whether the username is already used or not
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('別のユーザー名を使用してください')
        
    
    # check whether the email is already used or not
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('別のメールアドレスを使用してください')

class PostForm(FlaskForm):
    # ▼▼▼ ラベルを日本語に変更 ▼▼▼
    image = FileField('写真を選択', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], '画像ファイルのみ選択できます')
    ])
    shop_name = StringField('お店の名前', validators=[DataRequired()])
    comment = TextAreaField('コメント', validators=[Optional()])
    submit = SubmitField('投稿する')
    
    shop_osm_id = HiddenField("OSM ID", validators=[DataRequired()])
    shop_latitude = HiddenField("Latitude", validators=[DataRequired()])
    shop_longitude = HiddenField("Longitude", validators=[DataRequired()])

class CommentForm(FlaskForm):
    comment_body = TextAreaField('コメント', validators=[DataRequired()])
    submit = SubmitField('コメント')