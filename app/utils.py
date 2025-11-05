import os
from datetime import datetime, timedelta

from flask import current_app
from flask_login import current_user

import qrcode

from functools import wraps
from flask import redirect, url_for, flash


# 登录且是管理员才能访问的装饰器（适配role字段）
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('您没有权限访问此页面（需要管理员权限）', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def is_admin():
    """检查当前用户是否为管理员"""
    return current_user.is_authenticated and current_user.is_admin


def get_space_path(space):
    """获取空间的完整路径"""
    path = [space.name]
    current = space.parent
    while current:
        path.insert(0, current.name)
        current = current.parent
    return '/'.join(path)


def is_overdue(record, days=10):
    """
    检查记录是否逾期
    默认超过10天未归还视为逾期
    """
    if record.return_time or record.status != 'using':
        return False
    return (datetime.utcnow() - record.start_time) > timedelta(days=days)


# 当前未使用
def format_datetime(dt, format='%Y-%m-%d %H:%M'):
    """格式化日期时间"""
    if not dt:
        return ''
    return dt.strftime(format)


# 当前未使用
def check_reservation_availability(item_id, start_date, end_date, exclude_id=None):
    """
    检查物品在指定时间段是否可预约
    exclude_id: 用于编辑预约时排除自身
    """
    from app.models import Reservation

    query = Reservation.query.filter_by(
        item_id=item_id,
        status='valid'
    ).filter(
        Reservation.reservation_start <= end_date,
        Reservation.reservation_end >= start_date
    )

    if exclude_id:
        query = query.filter(Reservation.id != exclude_id)

    return query.first() is None


def generate_and_save_item_qrcode(item_id):
    """生成物品二维码并保存到static/qrcodes目录，返回相对路径（如qrcodes/item_1_qrcode.png）"""
    # 构建物品详情页URL（替换为实际访问地址）
    url = f"http://192.168.1.101:8080/items/{item_id}"  # 替换为你的局域网IP或域名
    # 生成二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # 定义存储路径（static/qrcodes目录）
    qr_dir = os.path.join(current_app.root_path, 'static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)  # 确保目录存在
    qr_filename = f"item_{item_id}_qrcode.png"
    qr_path = os.path.join(qr_dir, qr_filename)
    img.save(qr_path)

    # 返回相对static目录的子路径（如qrcodes/item_1_qrcode.png）
    return os.path.join('qrcodes', qr_filename)