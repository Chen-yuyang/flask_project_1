from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app import db
from app.models import Item, Reservation
from app.forms.reservation_forms import ReservationForm

bp = Blueprint('reservations', __name__)


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约"""
    status = request.args.get('status', '')
    reservations_query = current_user.reservations.order_by(Reservation.reservation_start)

    if status:
        reservations_query = reservations_query.filter(Reservation.status == status)

    reservations = reservations_query.all()
    return render_template('reservations/my_reservations.html', reservations=reservations)


@bp.route('/item/<int:item_id>')
@login_required
def item_reservations(item_id):
    """查看特定物品的所有预约"""
    item = Item.query.get_or_404(item_id)

    # 管理员可以查看所有预约，普通用户只能查看自己的
    if current_user.is_admin():
        reservations = Reservation.query.filter_by(item_id=item_id).order_by(Reservation.reservation_start).all()
    else:
        reservations = Reservation.query.filter_by(
            item_id=item_id,
            user_id=current_user.id
        ).order_by(Reservation.reservation_start).all()

    return render_template('reservations/item_reservations.html',
                           reservations=reservations,
                           item=item)


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    """创建物品预约"""
    item = Item.query.get_or_404(item_id)

    # 检查物品状态
    if item.status != 'available':
        flash(f'物品 "{item.name}" 当前不可预约，状态：{item.status}')
        return redirect(url_for('items.view', id=item_id))

    form = ReservationForm()

    # 设置默认预约时间为今天开始，持续3天
    if not form.reservation_start.data:
        form.reservation_start.data = datetime.now().date()
    if not form.reservation_end.data:
        form.reservation_end.data = (datetime.now() + timedelta(days=3)).date()

    if form.validate_on_submit():
        # 检查该时间段是否已有预约
        overlapping = Reservation.query.filter_by(
            item_id=item_id,
            status='valid'
        ).filter(
            Reservation.reservation_start <= form.reservation_end.data,
            Reservation.reservation_end >= form.reservation_start.data
        ).first()

        if overlapping:
            flash('该时间段已有预约，请选择其他时间')
            return render_template('reservations/create.html', form=form, item=item)

        # 创建预约
        reservation = Reservation(
            item_id=item_id,
            user_id=current_user.id,
            reservation_start=datetime.combine(form.reservation_start.data, datetime.min.time()),
            reservation_end=datetime.combine(form.reservation_end.data, datetime.max.time()),
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
