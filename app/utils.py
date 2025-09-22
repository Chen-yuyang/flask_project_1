from datetime import datetime, timedelta
from flask_login import current_user


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
        status='valid'
    ).filter(
        Reservation.reservation_start <= end_date,
        Reservation.reservation_end >= start_date
    )

    if exclude_id:
        query = query.filter(Reservation.id != exclude_id)

    return query.first() is None
