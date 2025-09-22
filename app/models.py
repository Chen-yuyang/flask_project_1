from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(10), default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    spaces = db.relationship('Space', backref='creator', lazy='dynamic')
    items = db.relationship('Item', backref='creator', lazy='dynamic')
    records = db.relationship('Record', backref='user', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('space.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    children = db.relationship('Space', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    items = db.relationship('Item', backref='space', lazy='dynamic', cascade="all, delete-orphan")

    def get_path(self):
        """获取空间的完整路径"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return '/'.join(path)

    def get_level(self):
        """获取空间层级"""
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    function = db.Column(db.Text)
    serial_number = db.Column(db.String(50), unique=True)
    status = db.Column(db.String(20), default='available')  # available, borrowed, reserved
    space_id = db.Column(db.Integer, db.ForeignKey('space.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    records = db.relationship('Record', backref='item', lazy='dynamic', cascade="all, delete-orphan")
    reservations = db.relationship('Reservation', backref='item', lazy='dynamic', cascade="all, delete-orphan")


class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    space_path = db.Column(db.String(255))
    usage_location = db.Column(db.String(255))
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    return_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='using')  # using, returned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_overdue(self):
        """检查是否逾期未还(10天)"""
        if self.status == 'using' and self.start_time:
            return datetime.utcnow() - self.start_time > timedelta(days=10)
        return False


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reservation_start = db.Column(db.DateTime, nullable=False)
    reservation_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='valid')  # valid, cancelled, used
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_active(self):
        """检查预约是否有效"""
        now = datetime.utcnow()
        return (self.status == 'valid' and
                self.reservation_start <= now <= self.reservation_end)
