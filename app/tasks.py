from datetime import datetime, timedelta
from flask import current_app  # 新增：用于日志输出
from app import db
from app.models import Reservation, Record
from app.email import send_email, send_overdue_reminder  # 合并导入，更简洁


def update_reservation_status():
    """更新预约状态的定时任务（去掉app_context参数，适配包装函数的上下文）"""
    try:
        current_app.logger.info("开始执行：更新预约状态任务")
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
                    res.item.status = 'reserved'  # 【新增】预约生效，锁定物品状态
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
        # 2. 处理 [冲突] (conflicted) -> [有效] / [作废]
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
                res.item.status = 'reserved'  # 【新增】冲突解除，锁定物品状态
                if res.user:
                    send_email(
                        to=res.user.email,
                        subject='预约已恢复有效',
                        template='reservations/email/reservation_reminder.html',  # 复用提醒模板
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
                # 【新增】如果物品当前状态是已预约（未被借走），则释放为可用
                if res.item.status == 'reserved':
                    res.item.status = 'available'

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
        current_app.logger.info("预约状态更新任务执行完成")

    except Exception as e:
        # 捕获所有异常，记录日志并回滚数据库，避免任务崩溃
        current_app.logger.error(f"更新预约状态任务执行失败: {str(e)}", exc_info=True)
        db.session.rollback()


def print_test_task():
    """测试定时任务：每5秒打印一次（去掉app_context参数）"""
    try:
        current_app.logger.info("===== 测试任务执行中 =====")
        current_app.logger.info(f"测试任务：当前UTC时间 {datetime.utcnow()}")
    except Exception as e:
        current_app.logger.error(f"测试任务执行失败: {str(e)}", exc_info=True)


def check_overdue_records():
    """检查逾期记录并发送提醒（去掉app_context参数）"""
    try:
        current_app.logger.info("开始执行：检查逾期记录任务")
        overdue_records = Record.query.filter(
            Record.status == 'using',
            Record._utc_start_time < datetime.utcnow() - timedelta(days=7)
        ).all()

        for record in overdue_records:
            send_overdue_reminder(record)

        current_app.logger.info(f"逾期记录检查完成，共找到 {len(overdue_records)} 条逾期记录")
    except Exception as e:
        current_app.logger.error(f"检查逾期记录任务执行失败: {str(e)}", exc_info=True)
        db.session.rollback()