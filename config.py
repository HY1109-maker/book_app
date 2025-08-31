import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABESE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir,'app.db')
    
    # データAPI
    OVERPASS_API_URL = 'https://overpass-api.de/api/interpreter'
    #　自然言語検索用のAPI
    NOMINATIM_API_URL = 'https://nominatim.openstreetmap.org/search'