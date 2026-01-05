from datetime import datetime, timedelta
from app import db
from app.models import Reservation, Record
from app.email import send_email

from app.email import send_overdue_reminder


def update_reservation_status(app_context):
    """更新预约状态的定时任务"""
    with app_context:  # 传入应用上下文，确保能访问 db 和配置
        now_utc = datetime.utcnow()

        # ===================================================
        # 1. 处理 [待开始] (scheduled) -> [有效] / [冲突]
        # ===================================================
        scheduled_res = Reservation.query.filter_by(status='scheduled').all()
        for res in scheduled_res:
            # 到达开始时间
            if now_utc >= res._utc_reservation_start:
                if res.item.status == 'available':
                    res.status = 'active'
                    # 可选：发送预约生效通知
                else:
                    res.status = 'conflicted'
                    # 发送冲突提醒：告知预约人物品未归还
                    if res.user:
                        send_email(
                            to=res.user.email,
                            subject='预约暂时冲突',
                            template='reservations/email/reservation_conflict.html',
                            item=res.item,
                            reservation=res
                        )
                db.session.commit()

        # ===================================================
        # 2. 处理 [冲突] (conflicted) -> [有效] / [作废] (新增逻辑)
        # ===================================================
        # 场景：前一个人迟还了，现在还了，预约应自动恢复为有效
        conflicted_res = Reservation.query.filter_by(status='conflicted').all()
        for res in conflicted_res:
            # 如果已经超过了预约结束时间，直接作废
            if now_utc >= res._utc_reservation_end:
                res.status = 'expired'
                db.session.commit()
                continue

            # 如果物品变回可用，且仍在预约时段内，恢复为有效
            if res.item.status == 'available':
                res.status = 'active'
                if res.user:
                    send_email(
                        to=res.user.email,
                        subject='预约已恢复有效',
                        template='reservations/email/reservation_reminder.html', # 复用提醒模板
                        reservation=res
                    )
                db.session.commit()

        # ===================================================
        # 3. 处理 [有效] (active) -> [作废] (expired)
        # ===================================================
        active_res = Reservation.query.filter_by(status='active').all()
        for res in active_res:
            # 判定条件：
            # A. 超过预约开始时间24小时仍未取走 (原有逻辑)
            # B. 或者已经超过了预约结束时间 (新增逻辑，预约时段已过)
            is_long_overdue = now_utc - res._utc_reservation_start > timedelta(hours=24)
            is_past_end_time = now_utc >= res._utc_reservation_end

            if is_long_overdue or is_past_end_time:
                res.status = 'expired'
                if res.user:
                    send_email(
                        to=res.user.email,
                        subject='预约已作废',
                        template='reservations/email/reservation_expired.html',
                        reservation=res
                    )
                db.session.commit()

        # ===================================================
        # 4. 预约前提醒 (scheduled)
        # ===================================================
        soon_res = Reservation.query.filter_by(status='scheduled').all()
        for res in soon_res:
            time_diff = res._utc_reservation_start - now_utc
            # 提前12小时提醒
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
    """检查逾期记录并发送提醒"""
    with app_context:
        overdue_records = Record.query.filter(
            Record.status == 'using',
            Record._utc_start_time < datetime.utcnow() - timedelta(days=7)
        ).all()

        for record in overdue_records:
            send_overdue_reminder(record)