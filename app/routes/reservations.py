import pytz

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import Item, Reservation
from app.forms.reservation_forms import ReservationForm

bp = Blueprint('reservations', __name__)

LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约"""
    status = request.args.get('status', '')
    reservations_query = current_user.reservations.order_by(Reservation._utc_reservation_start)

    if status:
        reservations_query = reservations_query.filter(Reservation.status == status)

    reservations = reservations_query.all()
    now_local = datetime.now(LOCAL_TIMEZONE)

    return render_template('reservations/my_reservations.html',
                           reservations=reservations,
                           now_local=now_local  # 后端传递当前本地时间
                           )


# 新增：所有预约（仅管理员）
@bp.route('/all')
@login_required
def all_reservations():
    # 权限控制：仅管理员可查看
    if not current_user.is_admin():
        flash('没有权限查看所有预约记录', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 可选：添加筛选条件（如按状态、物品、用户筛选）
    status = request.args.get('status', '')
    item_id = request.args.get('item_id', '')
    user_id = request.args.get('user_id', '')

    # 构建查询（按预约开始时间倒序）
    reservations_query = Reservation.query.order_by(Reservation._utc_reservation_start.desc())

    # 筛选逻辑
    if status:
        reservations_query = reservations_query.filter(Reservation.status == status)
    if item_id:
        reservations_query = reservations_query.filter(Reservation.item_id == item_id)
    if user_id:
        reservations_query = reservations_query.filter(Reservation.user_id == user_id)

    reservations = reservations_query.all()
    # 传递所有物品列表（用于筛选下拉框）
    all_items = Item.query.all()

    return render_template(
        'reservations/all_reservations.html',
        reservations=reservations,
        all_items=all_items,
        current_status=status,
        current_item_id=item_id,
        current_user_id=user_id
    )


# 关键：路由函数名必须是 item_reservations（与模板中的端点后缀一致）
@bp.route('/item/<int:item_id>')  # 确保路由参数是 item_id
@login_required
def item_reservations(item_id):  # 函数名必须是 item_reservations
    """查看特定物品的所有预约"""
    item = Item.query.get_or_404(item_id)

    now_local = datetime.now(LOCAL_TIMEZONE)  # 关键：后端提前算好，传给模板

    # 权限逻辑（管理员查看所有，普通用户查看自己的）
    if current_user.is_admin():
        reservations = Reservation.query.filter_by(item_id=item_id).order_by(Reservation._utc_reservation_start).all()
    else:
        reservations = Reservation.query.filter_by(
            item_id=item_id,
            user_id=current_user.id
        ).order_by(Reservation._utc_reservation_start).all()

    return render_template('reservations/item_reservations.html',
                           reservations=reservations,
                           item=item,
                           now_local=now_local
                           )


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    item = Item.query.get_or_404(item_id)
    form = ReservationForm()

    if form.validate_on_submit():
        # 1. 将东八区aware时间转换为UTC时间（数据库存储UTC）
        start_local = form.reservation_start.data
        start_utc = start_local.astimezone(pytz.utc)
        end_local = form.reservation_end.data
        end_utc = end_local.astimezone(pytz.utc)

        # 2. 检查重叠预约（基于UTC时间与数据库UTC字段比较）
        overlapping = Reservation.query.filter_by(
            item_id=item_id,
            status='valid'
        ).filter(
            Reservation._utc_reservation_start < end_utc,
            Reservation._utc_reservation_end > start_utc
        ).first()

        if overlapping:
            flash('该时间段已有预约，请选择其他时间')
            return render_template('reservations/create.html', form=form, item=item)

        # 3. 创建预约记录（存入UTC时间）
        reservation = Reservation(
            item_id=item_id,
            user_id=current_user.id,
            _utc_reservation_start=start_utc,
            _utc_reservation_end=end_utc,
            notes=form.notes.data,
            status='valid'
        )

        db.session.add(reservation)
        db.session.commit()

        flash(f'成功预约物品 "{item.name}"')
        return redirect(url_for('reservations.item_reservations', item_id=item_id))

    return render_template('reservations/create.html', form=form, item=item)


@bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    """取消预约"""
    reservation = Reservation.query.get_or_404(reservation_id)

    # 检查权限
    if not current_user.is_admin() and reservation.user_id != current_user.id:
        flash('没有权限执行此操作')
        return redirect(url_for('reservations.my_reservations'))

    # 检查预约状态
    if reservation.status != 'valid':
        flash('该预约已取消或已使用')
        return redirect(url_for('reservations.my_reservations'))

    reservation.status = 'cancelled'
    db.session.commit()

    flash('预约已取消')
    return redirect(url_for('reservations.my_reservations'))
