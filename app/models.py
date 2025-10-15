from datetime import datetime, timedelta

import pytz
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# 关键修改：使用 itsdangerous 2.2.0+ 推荐的 URLSafeTimedSerializer
from itsdangerous import URLSafeTimedSerializer as Serializer


class User(UserMixin, db.Model):
    # 原有字段和方法保持不变...
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(10), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_reset_password_token(self, expires_in=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        # 关键修改：移除 .decode('utf-8')，因为 dumps() 已返回字符串
        return s.dumps({'user_id': self.id})  # 直接返回字符串令牌
    # 关系
    spaces = db.relationship('Space', backref='creator', lazy='dynamic')
    items = db.relationship('Item', backref='creator', lazy='dynamic')
    records = db.relationship('Record', backref='user', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    @classmethod
    def verify_reset_password_token(cls, token, max_age=3600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=max_age)
        except:
            return None
        return cls.query.get(data['user_id'])

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
    # 新增：存储二维码图片路径
    barcode_path = db.Column(db.String(255))
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
    start_time = db.Column(db.DateTime, default=datetime.utcnow)  # 数据库存UTC时间
    return_time = db.Column(db.DateTime)  # 数据库存UTC时间（可为空）
    status = db.Column(db.String(20), default='using')  # using, returned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 数据库存UTC时间

    # 新增1：将UTC开始时间转换为东八区（北京时间）
    def local_start_time(self):
        """
        返回东八区本地时间（与电脑显示一致）
        格式：datetime对象，可直接用于strftime格式化
        """
        # 定义东八区时区（固定，不依赖app配置，避免配置缺失问题）
        local_timezone = pytz.timezone('Asia/Shanghai')
        # 将UTC时间（无时区信息）添加UTC时区标识，再转换为东八区
        utc_time = pytz.utc.localize(self.start_time)  # 给start_time添加UTC时区
        return utc_time.astimezone(local_timezone)  # 转换为东八区

    # 新增2：将UTC归还时间转换为东八区（北京时间），处理return_time为None的情况
    def local_return_time(self):
        """
        返回东八区本地时间（与电脑显示一致），若未归还则返回None
        """
        if not self.return_time:  # 未归还时，return_time为None
            return None
        local_timezone = pytz.timezone('Asia/Shanghai')
        utc_time = pytz.utc.localize(self.return_time)
        return utc_time.astimezone(local_timezone)

    # 原有方法：检查是否逾期（无需修改，基于UTC时间判断，逻辑正确）
    def is_overdue(self):
        """检查是否逾期未还(10天)"""
        if self.status == 'using' and self.start_time:
            # 用UTC时间比较，避免时区偏差导致的逾期判断错误
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
