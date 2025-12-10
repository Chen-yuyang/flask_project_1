from datetime import datetime, timedelta
from app import db
from app.models import Reservation, Record
from app.email import send_email

from app.email import send_overdue_reminder


def update_reservation_status(app_context):
    """更新预约状态的定时任务"""
    with app_context:  # 传入应用上下文，确保能访问 db 和配置
        now_utc = datetime.utcnow()

        # 1. 待开始(scheduled) → 有效/冲突
        scheduled_res = Reservation.query.filter_by(status='scheduled').all()
        for res in scheduled_res:
            if now_utc >= res._utc_reservation_start:
                if res.item.status == 'available':
                    res.status = 'active'
                else:
                    res.status = 'conflicted'
                    # 发送冲突提醒
                    active_record = Record.query.filter_by(item_id=res.item.id, status='using').first()
                    if active_record and active_record.user:
                        send_email(
                            to=active_record.user.email,
                            subject='物品归还提醒',
                            template='reservations/email/reservation_conflict.html',
                            item=res.item,
                            reservation=res
                        )
                db.session.commit()

        # 2. 有效(active) → 作废(expired)
        active_res = Reservation.query.filter_by(status='active').all()
        for res in active_res:
            if now_utc - res._utc_reservation_start > timedelta(hours=24):
                res.status = 'expired'
                if res.user:
                    send_email(
                        to=res.user.email,
                        subject='预约已作废',
                        template='reservations/email/reservation_expired.html',
                        reservation=res
                    )
                db.session.commit()

        # 3. 预约前12小时提醒
        soon_res = Reservation.query.filter_by(status='scheduled').all()
        for res in soon_res:
            time_diff = res._utc_reservation_start - now_utc
            if timedelta(hours=12) >= time_diff > timedelta(hours=11):
                if res.user:
                    send_email(
                        to=res.user.email,
                        subject='预约即将开始',
                        template='reservations/email/reservation_reminder.html',
                        reservation=res
                    )


def print_test_task(app_context):
    """测试定时任务：每5秒打印一次"""
    with app_context:
        from flask import current_app
        # 用 logger 打印（比 print 更规范，且会包含时间戳）
        current_app.logger.info(f"===== 测试任务执行中 =====")
        current_app.logger.info(f"测试任务：当前UTC时间 {datetime.utcnow()}")


def check_overdue_records(app_context):
    """检查逾期记录并发送提醒（修复数据库字段引用）"""
    with app_context:
        # 关键修改：使用数据库实际存储的 _utc_start_time 字段（而非 property 的 start_time）
        overdue_records = Record.query.filter(
            Record.status == 'using',
            # 直接用数据库里的 UTC 时间字段比较，与模型的 is_overdue 逻辑一致
            Record._utc_start_time < datetime.utcnow() - timedelta(days=7)
        ).all()

        for record in overdue_records:
            send_overdue_reminder(record)