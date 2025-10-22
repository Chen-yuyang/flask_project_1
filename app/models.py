from datetime import datetime, timedelta
import pytz  # 确保已安装：pip install pytz
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
# 关键修改：使用 itsdangerous 2.2.0+ 推荐的 URLSafeTimedSerializer
from itsdangerous import URLSafeTimedSerializer as Serializer

# 全局定义本地时区（东八区，北京时间）
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(10), default='user')

    # 数据库存储UTC时间（字段名加前缀_utc，实际数据库列名仍为created_at）
    _utc_created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)

    # 定义property，前端调用user.created_at时自动返回本地时间
    @property
    def created_at(self):
        return self._convert_utc_to_local(self._utc_created_at)

    # 时间转换通用方法（UTC→本地时区）
    def _convert_utc_to_local(self, utc_time):
        if not utc_time:
            return None
        # 给UTC时间添加时区标识，再转换为本地时区
        utc_aware = pytz.utc.localize(utc_time)  # 标记为UTC时间
        return utc_aware.astimezone(LOCAL_TIMEZONE)  # 转换为本地时间

    # 其他原有方法保持不变...
    def get_reset_password_token(self, expires_in=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @classmethod
    def verify_reset_password_token(cls, token, max_age=3600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=max_age)
        except:
            return None
        return cls.query.get(data['user_id'])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    # 关系
    spaces = db.relationship('Space', backref='creator', lazy='dynamic')
    items = db.relationship('Item', backref='creator', lazy='dynamic')
    records = db.relationship('Record', backref='user', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='user', lazy='dynamic')


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('space.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # 数据库存储UTC时间
    _utc_created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)

    # 前端调用space.created_at时返回本地时间
    @property
    def created_at(self):
        if not self._utc_created_at:
            return None
        utc_aware = pytz.utc.localize(self._utc_created_at)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    # 原有方法保持不变...
    def get_path(self):
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return '/'.join(path)

    def get_level(self):
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level

    # 关系
    children = db.relationship('Space', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    items = db.relationship('Item', backref='space', lazy='dynamic', cascade="all, delete-orphan")


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    function = db.Column(db.Text)
    serial_number = db.Column(db.String(50), unique=True)
    status = db.Column(db.String(20), default='available')
    barcode_path = db.Column(db.String(255))
    space_id = db.Column(db.Integer, db.ForeignKey('space.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # 数据库存储UTC时间
    _utc_created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    _utc_updated_at = db.Column('updated_at', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 前端调用item.created_at / item.updated_at时返回本地时间
    @property
    def created_at(self):
        if not self._utc_created_at:
            return None
        utc_aware = pytz.utc.localize(self._utc_created_at)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    @property
    def updated_at(self):
        if not self._utc_updated_at:
            return None
        utc_aware = pytz.utc.localize(self._utc_updated_at)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    # 关系
    records = db.relationship('Record', backref='item', lazy='dynamic', cascade="all, delete-orphan")
    reservations = db.relationship('Reservation', backref='item', lazy='dynamic', cascade="all, delete-orphan")


class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    space_path = db.Column(db.String(255))
    usage_location = db.Column(db.String(255))

    # 数据库存储UTC时间
    _utc_start_time = db.Column('start_time', db.DateTime, default=datetime.utcnow)
    _utc_return_time = db.Column('return_time', db.DateTime)
    _utc_created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='using')

    # 前端调用record.start_time / return_time / created_at时返回本地时间
    @property
    def start_time(self):
        if not self._utc_start_time:
            return None
        utc_aware = pytz.utc.localize(self._utc_start_time)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    @property
    def return_time(self):
        if not self._utc_return_time:
            return None
        utc_aware = pytz.utc.localize(self._utc_return_time)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    @property
    def created_at(self):
        if not self._utc_created_at:
            return None
        utc_aware = pytz.utc.localize(self._utc_created_at)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    # 逾期判断基于UTC时间（逻辑不变，确保准确性）
    def is_overdue(self):
        if self.status == 'using' and self._utc_start_time:  # 使用数据库原始UTC时间判断
            return datetime.utcnow() - self._utc_start_time > timedelta(days=10)
        return False


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # 数据库存储UTC时间
    _utc_reservation_start = db.Column('reservation_start', db.DateTime, nullable=False)
    _utc_reservation_end = db.Column('reservation_end', db.DateTime, nullable=False)
    _utc_created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='valid')

    # 前端调用reservation.reservation_start / end / created_at时返回本地时间
    @property
    def reservation_start(self):
        if not self._utc_reservation_start:
            return None
        utc_aware = pytz.utc.localize(self._utc_reservation_start)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    @property
    def reservation_end(self):
        if not self._utc_reservation_end:
            return None
        utc_aware = pytz.utc.localize(self._utc_reservation_end)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    @property
    def created_at(self):
        if not self._utc_created_at:
            return None
        utc_aware = pytz.utc.localize(self._utc_created_at)
        return utc_aware.astimezone(LOCAL_TIMEZONE)

    # 预约有效性判断基于UTC时间（逻辑不变）
    def is_active(self):
        now = datetime.utcnow()
        return (self.status == 'valid' and
                self._utc_reservation_start <= now <= self._utc_reservation_end)  # 使用数据库原始UTC时间