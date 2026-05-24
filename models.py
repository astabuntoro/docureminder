from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from datetime import date, datetime

db     = SQLAlchemy()
bcrypt = Bcrypt()

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # Gmail SMTP settings (stored per-user)
    gmail_address = db.Column(db.String(150))
    gmail_app_password = db.Column(db.String(200))   # Google App Password
    # Notification preferences
    notify_days   = db.Column(db.String(50), default='90,30,7,1')  # days-before thresholds
    email_notify  = db.Column(db.Boolean, default=True)
    push_notify   = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    documents     = db.relationship('Document', backref='owner_user', lazy=True, cascade='all, delete-orphan')
    push_subs     = db.relationship('PushSubscription', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode()

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    @property
    def notify_days_list(self):
        return [int(x) for x in self.notify_days.split(',') if x.strip().isdigit()]


class Document(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name         = db.Column(db.String(100), nullable=False)
    doc_type     = db.Column(db.String(50), nullable=False)
    doc_number   = db.Column(db.String(100))
    person_name  = db.Column(db.String(100))
    issued_date  = db.Column(db.Date)
    expiry_date  = db.Column(db.Date, nullable=False)
    notes        = db.Column(db.Text)
    file_paths   = db.Column(db.Text, default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def files(self):
        return [f for f in (self.file_paths or '').split('\n') if f.strip()]

    @property
    def days_left(self):
        return (self.expiry_date - date.today()).days

    @property
    def status(self):
        d = self.days_left
        if d < 0:   return 'expired'
        if d <= 30: return 'critical'
        if d <= 90: return 'warning'
        return 'active'

    @property
    def status_label(self):
        return {'expired':'Kedaluwarsa','critical':'Segera Habis',
                'warning':'Perlu Perhatian','active':'Aktif'}[self.status]


class PushSubscription(db.Model):
    """Stores browser push subscription endpoint per device per user."""
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh   = db.Column(db.Text, nullable=False)
    auth     = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
