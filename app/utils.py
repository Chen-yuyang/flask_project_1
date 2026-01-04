import os
import re
from datetime import datetime, timedelta

from flask import current_app, redirect, url_for, flash
from flask_login import current_user
from functools import wraps
import qrcode


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


def format_datetime(dt, format='%Y-%m-%d %H:%M'):
    """格式化日期时间"""
    if not dt:
        return ''
    return dt.strftime(format)


def check_reservation_availability(item_id, start_date, end_date, exclude_id=None):
    """
    检查物品在指定时间段是否可预约
    exclude_id: 用于编辑预约时排除自身
    """
    from app.models import Reservation

    query = Reservation.query.filter_by(
        item_id=item_id,
        status='active'
    ).filter(
        Reservation.reservation_start <= end_date,
        Reservation.reservation_end >= start_date
    )

    if exclude_id:
        query = query.filter(Reservation.id != exclude_id)

    return query.first() is None


def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    # 替换 Windows/Linux 文件系统中的非法字符为空
    return re.sub(r'[\\/*?:"<>|]', "", str(filename)).strip()


def generate_and_save_item_qrcode(item):
    """
    生成物品二维码并保存到static/qrcodes目录
    文件名格式：物品名称_编号.png
    """
    # 1. 获取配置的 Base URL
    base_url = current_app.config.get('QR_CODE_BASE_URL', 'http://127.0.0.1:5000')
    base_url = base_url.rstrip('/')  # 去除末尾斜杠

    # 2. 构建物品详情页URL
    url = f"{base_url}/items/{item.id}"

    # 3. 生成二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # 4. 构建文件名 (物品名称_编号.png)
    safe_name = sanitize_filename(item.name)
    safe_serial = sanitize_filename(item.serial_number)
    # 如果文件名为空，回退到使用ID
    if not safe_name or not safe_serial:
        filename = f"item_{item.id}_qrcode.png"
    else:
        filename = f"{safe_name}_{safe_serial}.png"

    # 5. 定义存储路径（static/qrcodes目录）
    qr_dir = os.path.join(current_app.root_path, 'static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)  # 确保目录存在

    qr_path = os.path.join(qr_dir, filename)
    img.save(qr_path)

    # 6. 返回相对static目录的子路径（如qrcodes/名称_编号.png）
    return os.path.join('qrcodes', filename)