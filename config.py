import os

class Config:
    SECRET_KEY         = os.environ.get('SECRET_KEY', 'docureminder-dev-secret-change-in-prod')

    # Database — Railway auto-sets DATABASE_URL as postgresql://
    # SQLAlchemy needs postgresql+psycopg2:// so we fix the URL if needed
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///docureminder.db')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif _db_url.startswith('postgresql://') and '+psycopg2' not in _db_url:
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    SQLALCHEMY_DATABASE_URI        = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads — local dev uses /uploads folder, production uses Cloudinary
    UPLOAD_FOLDER       = os.path.join(os.path.dirname(__file__), 'uploads')
    USE_CLOUDINARY      = bool(os.environ.get('CLOUDINARY_CLOUD_NAME'))
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    # VAPID keys for Web Push
    VAPID_PRIVATE_KEY  = os.environ.get('VAPID_PRIVATE_KEY', 'gjemyqPjBB9ZnQ6Hwk2KfMmr67XPY-p_nRGgXjk51Jk')
    VAPID_PUBLIC_KEY   = os.environ.get('VAPID_PUBLIC_KEY',  'BJKRaTbolHFwBcWKZcnYVzFu4Seib0Q2CPtSCNbgqpr00nqCQagmF3ozx6ry1oAINO1mET3WfyzbAxINdXTzhSQ')
    VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@docureminder.app')

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT   = 587
