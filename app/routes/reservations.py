import pytz
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_

from app import db
from app.models import Item, Reservation, Record
from app.forms.reservation_forms import ReservationForm
from app.email import send_email

bp = Blueprint('reservations', __name__)
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


# 辅助函数：更新预约状态（充分使用模型方法）
def update_reservation_status():
    """自动更新预约状态（应作为定时任务每小时执行一次）"""
    now_utc = datetime.utcnow()

    # 1. 待开始(scheduled) → 有效/冲突：到达预约起始时间
    # 直接筛选status='scheduled'的预约，无需调用is_scheduled方法
    scheduled_res = Reservation.query.filter_by(status='scheduled').all()
    for res in scheduled_res:
        if now_utc >= res._utc_reservation_start:  # 仅判断时间是否到达
            if res.item.status == 'available':
                res.status = 'active'  # 物品可用→有效
            else:
                res.status = 'conflicted'  # 物品占用→冲突
                # 发送冲突提醒给上一使用者
                active_record = Record.query.filter_by(item_id=res.item.id, status='using').first()
                if active_record and active_record.user:
                    send_email(
                        recipient=active_record.user.email,
                        subject='物品归还提醒',
                        template='email/reservation_conflict',
                        item=res.item,
                        reservation=res
                    )
            db.session.commit()

    # 2. 有效(active) → 作废(expired)：超24小时未使用
    active_res = Reservation.query.filter_by(status='active').all()
    for res in active_res:
        if res.is_expired():
            res.status = 'expired'
            if res.user:
                send_email(
                    recipient=res.user.email,
                    subject='预约已作废',
                    template='email/reservation_expired',
                    reservation=res
                )
            db.session.commit()

    # 3. 预约前12小时提醒
    soon_res = Reservation.query.filter_by(status='scheduled').all()
    for res in soon_res:
        # 调用is_scheduled判断是否仍为待开始状态（未到达起始时间）
        if res.is_scheduled():
            time_diff = res._utc_reservation_start - now_utc
            if timedelta(hours=12) >= time_diff > timedelta(hours=11):
                if res.user:
                    send_email(
                        recipient=res.user.email,
                        subject='预约即将开始',
                        template='email/reservation_reminder',
                        reservation=res
                    )


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约（支持新状态筛选）"""
    update_reservation_status()

    status = request.args.get('status', '')
    reservations_query = current_user.reservations.order_by(Reservation._utc_reservation_start)

    # 状态筛选（保留原逻辑，查询时仍用status字段）
    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)

    reservations = reservations_query.all()
    now_local = datetime.now(LOCAL_TIMEZONE)

    return render_template('reservations/my_reservations.html',
                           reservations=reservations,
                           now_local=now_local
                           )


@bp.route('/all')
@login_required
def all_reservations():
    """查看所有预约（仅管理员）"""
    if not current_user.is_admin():
        flash('没有权限查看所有预约记录', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    update_reservation_status()

    status = request.args.get('status', '')
    item_id = request.args.get('item_id', '')
    user_id = request.args.get('user_id', '')

    reservations_query = Reservation.query.order_by(Reservation._utc_reservation_start.desc())

    # 筛选逻辑（查询时用status字段，实例判断用模型方法）
    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)
    if item_id:
        reservations_query = reservations_query.filter(Reservation.item_id == item_id)
    if user_id:
        reservations_query = reservations_query.filter(Reservation.user_id == user_id)

    reservations = reservations_query.all()
    all_items = Item.query.all()

    return render_template(
        'reservations/all_reservations.html',
        reservations=reservations,
        all_items=all_items,
        current_status=status,
        current_item_id=item_id,
        current_user_id=user_id
    )


@bp.route('/item/<int:item_id>')
@login_required
def item_reservations(item_id):
    """查看特定物品的所有预约"""
    item = Item.query.get_or_404(item_id)
    now_local = datetime.now(LOCAL_TIMEZONE)
    update_reservation_status()

    # 权限逻辑
    if current_user.is_admin():
        reservations = Reservation.query.filter_by(item_id=item_id).order_by(Reservation._utc_reservation_start).all()
    else:
        reservations = current_user.reservations.filter_by(item_id=item_id).order_by(Reservation._utc_reservation_start).all()

    return render_template('reservations/item_reservations.html',
                           reservations=reservations,
                           item=item,
                           now_local=now_local
                           )


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    """创建预约（用模型方法辅助校验）"""
    item = Item.query.get_or_404(item_id)
    form = ReservationForm()

    if form.validate_on_submit():
        # 时间转换
        start_local = form.reservation_start.data
        start_utc = start_local.astimezone(pytz.utc)
        end_local = form.reservation_end.data
        end_utc = end_local.astimezone(pytz.utc)

        # 检查重叠预约（筛选占用时间段的状态，用or_组合条件）
        overlapping = Reservation.query.filter_by(item_id=item_id).filter(
            or_(
                Reservation.status == 'scheduled',
                Reservation.status == 'active',
                Reservation.status == 'conflicted'
            ),
            Reservation._utc_reservation_start < end_utc,
            Reservation._utc_reservation_end > start_utc
        ).first()

        if overlapping:
            flash('该时间段已有预约，请选择其他时间', 'danger')
            return render_template('reservations/create.html', form=form, item=item)

        # 创建预约（初始状态scheduled）
        reservation = Reservation(
            item_id=item_id,
            user_id=current_user.id,
            _utc_reservation_start=start_utc,
            _utc_reservation_end=end_utc,
            notes=form.notes.data,
            status='scheduled'
        )

        db.session.add(reservation)
        db.session.commit()

        flash(f'成功预约物品 "{item.name}"，状态：待开始', 'success')
        return redirect(url_for('reservations.item_reservations', item_id=item_id))

    return render_template('reservations/create.html', form=form, item=item)


@bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    """取消预约（用模型方法判断是否可取消）"""
    reservation = Reservation.query.get_or_404(reservation_id)

    # 权限检查
    if not current_user.is_admin() and reservation.user_id != current_user.id:
        flash('没有权限执行此操作', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 状态检查：用模型方法判断是否为待开始/有效状态（更精准）
    if not (reservation.is_scheduled() or reservation.is_active()):
        status_cn = {
            'scheduled': '待开始', 'active': '有效', 'conflicted': '冲突',
            'expired': '已作废', 'cancelled': '已取消', 'used': '已使用'
        }.get(reservation.status, reservation.status)
        flash(f'该预约状态为「{status_cn}」，无法取消', 'warning')
        return redirect(url_for('reservations.my_reservations'))

    reservation.status = 'cancelled'
    db.session.commit()

    flash('预约已取消', 'success')
    return redirect(url_for('reservations.my_reservations'))


@bp.route('/use/<int:reservation_id>', methods=['POST'])
@login_required
def use_reservation(reservation_id):
    """使用预约（核心用模型is_active()判断，包含物品可用性校验）"""
    reservation = Reservation.query.get_or_404(reservation_id)

    # 权限检查
    if reservation.user_id != current_user.id:
        flash('没有权限使用此预约', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 状态检查：直接用模型方法（包含状态+物品可用性+时间范围校验）
    if not reservation.is_active():
        status_cn = {
            'scheduled': '待开始', 'active': '有效', 'conflicted': '冲突',
            'expired': '已作废', 'cancelled': '已取消', 'used': '已使用'
        }.get(reservation.status, reservation.status)
        flash(f'仅「有效且物品可用」的预约可使用，当前状态：{status_cn}', 'warning')
        return redirect(url_for('reservations.my_reservations'))

    # 标记为已使用
    reservation.status = 'used'
    db.session.commit()

    flash('预约已转为使用状态，请在借用记录中完成登记', 'success')
    return redirect(url_for('records.create', item_id=reservation.item_id))