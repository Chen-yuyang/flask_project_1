from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pytz

from app import db
from app.models import Reservation, Item, User
from app.forms.reservation_forms import ReservationForm

bp = Blueprint('reservations', __name__)

# 定义与 models.py 一致的本地时区
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约"""
    status = request.args.get('status', '')
    item_name = request.args.get('item_name', '').strip()

    # 基础查询
    query = current_user.reservations

    # 筛选状态
    if status:
        query = query.filter(Reservation.status == status)

    # 筛选物品名称 (模糊查询)
    if item_name:
        query = query.join(Item).filter(Item.name.ilike(f'%{item_name}%'))

    # 按开始时间倒序排列
    reservations = query.order_by(Reservation._utc_reservation_start.desc()).all()

    # 修复：传递带时区的当前时间 (datetime.now(LOCAL_TIMEZONE))
    # 这样在模板中与 reservation.reservation_start (也是带时区的) 相减时就不会报错了
    return render_template('reservations/my_reservations.html',
                           reservations=reservations,
                           current_status=status,
                           now_local=datetime.now(LOCAL_TIMEZONE))


@bp.route('/all')
@login_required
def all_reservations():
    """管理员查看所有预约"""
    if not current_user.is_admin():
        flash('没有权限查看所有预约')
        return redirect(url_for('reservations.my_reservations'))

    status = request.args.get('status', '')
    item_name = request.args.get('item_name', '').strip()
    username = request.args.get('username', '').strip()

    query = Reservation.query

    # 筛选状态
    if status:
        query = query.filter(Reservation.status == status)

    # 筛选物品名称 (联表模糊查询)
    if item_name:
        query = query.join(Item).filter(Item.name.ilike(f'%{item_name}%'))

    # 筛选用户名 (联表模糊查询)
    if username:
        query = query.join(User).filter(User.username.ilike(f'%{username}%'))

    # 按开始时间倒序
    reservations = query.order_by(Reservation._utc_reservation_start.desc()).all()

    return render_template('reservations/all_reservations.html',
                           reservations=reservations,
                           current_status=status)


@bp.route('/item/<int:item_id>')
@login_required
def item_reservations(item_id):
    """查看特定物品的预约"""
    item = Item.query.get_or_404(item_id)

    reservations = Reservation.query.filter_by(item_id=item_id).order_by(
        Reservation._utc_reservation_start.desc()).all()

    # 修复：同样传递带时区的当前时间
    return render_template('reservations/item_reservations.html',
                           item=item,
                           reservations=reservations,
                           now_local=datetime.now(LOCAL_TIMEZONE))


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    item = Item.query.get_or_404(item_id)
    form = ReservationForm()

    if form.validate_on_submit():
        start_time = form.start_time.data
        end_time = form.end_time.data

        # 1. 基础校验：开始时间必须在未来
        if start_time < datetime.now():
            flash('预约开始时间不能早于当前时间')
            return render_template('reservations/create.html', form=form, item=item)

        # 2. 基础校验：结束时间必须晚于开始时间
        if end_time <= start_time:
            flash('结束时间必须晚于开始时间')
            return render_template('reservations/create.html', form=form, item=item)

        # 3. 冲突检测
        conflicts = Reservation.query.filter(
            Reservation.item_id == item_id,
            Reservation.status.in_(['scheduled', 'active']),
            Reservation._utc_reservation_start < end_time,
            Reservation._utc_reservation_end > start_time
        ).first()

        if conflicts:
            flash(f'该时间段已被用户 {conflicts.user.username} 预约，请调整时间')
            return render_template('reservations/create.html', form=form, item=item)

        # 创建预约
        reservation = Reservation(
            item_id=item_id,
            user_id=current_user.id,
            start_time=start_time,
            end_time=end_time,
            notes=form.notes.data,
            status='scheduled'
        )

        db.session.add(reservation)
        db.session.commit()

        flash('预约成功！')
        return redirect(url_for('reservations.my_reservations'))

    return render_template('reservations/create.html', form=form, item=item)


@bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)

    if not current_user.is_admin() and reservation.user_id != current_user.id:
        flash('没有权限取消此预约')
        return redirect(url_for('reservations.my_reservations'))

    if reservation.status not in ['scheduled', 'active']:
        flash('该预约当前状态不可取消')
        return redirect(url_for('reservations.my_reservations'))

    reservation.status = 'cancelled'
    db.session.commit()
    flash('预约已取消')

    return redirect(request.referrer or url_for('reservations.my_reservations'))


@bp.route('/use/<int:reservation_id>', methods=['POST'])
@login_required
def use_reservation(reservation_id):
    """通过预约快速创建使用记录"""
    reservation = Reservation.query.get_or_404(reservation_id)

    if reservation.user_id != current_user.id:
        flash('无权操作')
        return redirect(url_for('reservations.my_reservations'))

    if not reservation.is_active():
        flash('预约尚未开始或已过期')
        return redirect(url_for('reservations.my_reservations'))

    from app.models import Record

    if reservation.item.status != 'available':
        flash('物品当前未处于空闲状态，无法开始使用')
        return redirect(url_for('reservations.my_reservations'))

    record = Record(
        item_id=reservation.item_id,
        user_id=current_user.id,
        space_path=reservation.item.space.get_path(),
        usage_location='预约使用',
        status='using'
    )

    reservation.item.status = 'borrowed'
    reservation.status = 'used'

    db.session.add(record)
    db.session.commit()

    flash('已开始使用物品')
    return redirect(url_for('records.my_records'))


@bp.route('/delete/<int:reservation_id>', methods=['POST'])
@login_required
def delete(reservation_id):
    """删除预约记录（仅管理员）"""
    if not current_user.is_admin():
        flash('没有权限执行此操作')
        return redirect(url_for('reservations.my_reservations'))

    reservation = Reservation.query.get_or_404(reservation_id)

    db.session.delete(reservation)
    db.session.commit()

    flash('预约记录已删除')
    return redirect(request.referrer or url_for('reservations.all_reservations'))