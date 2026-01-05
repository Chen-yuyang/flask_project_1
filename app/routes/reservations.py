import pytz
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_

from app import db
from app.models import Item, Reservation, Record, User
from app.forms.reservation_forms import ReservationForm

bp = Blueprint('reservations', __name__)
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约（支持分页、状态和物品筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10条

    status = request.args.get('status', '')
    item_id = request.args.get('item_id', '')

    # 构建查询
    reservations_query = current_user.reservations

    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)

    if item_id:
        reservations_query = reservations_query.filter(Reservation.item_id == item_id)

    reservations_query = reservations_query.order_by(Reservation._utc_reservation_start.desc())

    # 使用分页
    pagination = reservations_query.paginate(page=page, per_page=per_page, error_out=False)
    reservations = pagination.items

    # 传递带时区的当前时间，防止模板计算剩余时间时报错
    now_local = datetime.now(LOCAL_TIMEZONE)

    return render_template('reservations/my_reservations.html',
                           reservations=reservations,
                           pagination=pagination,
                           now_local=now_local,
                           current_status=status,
                           current_item_id=item_id)


@bp.route('/all')
@login_required
def all_reservations():
    """查看所有预约（仅管理员，支持分页）"""
    if not current_user.is_admin():
        flash('没有权限查看所有预约记录', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    page = request.args.get('page', 1, type=int)
    per_page = 15  # 管理员每页15条

    # 获取筛选参数（改为文本输入筛选，避免下拉框过长）
    status = request.args.get('status', '')
    item_name = request.args.get('item_name', '').strip()
    username = request.args.get('username', '').strip()

    reservations_query = Reservation.query

    # 状态筛选
    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)

    # 物品名称模糊筛选
    if item_name:
        reservations_query = reservations_query.join(Item).filter(Item.name.ilike(f'%{item_name}%'))

    # 用户名模糊筛选
    if username:
        reservations_query = reservations_query.join(User).filter(User.username.ilike(f'%{username}%'))

    reservations_query = reservations_query.order_by(Reservation._utc_reservation_start.desc())

    # 执行分页
    pagination = reservations_query.paginate(page=page, per_page=per_page, error_out=False)
    reservations = pagination.items

    return render_template(
        'reservations/all_reservations.html',
        reservations=reservations,
        pagination=pagination,
        current_status=status
    )


@bp.route('/item/<int:item_id>')
@login_required
def item_reservations(item_id):
    """查看特定物品的所有预约（支持分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = 10

    item = Item.query.get_or_404(item_id)
    now_local = datetime.now(LOCAL_TIMEZONE)

    # 权限逻辑
    if current_user.is_admin():
        query = Reservation.query.filter_by(item_id=item_id)
    else:
        query = current_user.reservations.filter_by(item_id=item_id)

    query = query.order_by(Reservation._utc_reservation_start.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    reservations = pagination.items

    return render_template('reservations/item_reservations.html',
                           reservations=reservations,
                           pagination=pagination,
                           item=item,
                           now_local=now_local)


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    """创建预约"""
    item = Item.query.get_or_404(item_id)
    form = ReservationForm()

    if form.validate_on_submit():
        start_local = form.reservation_start.data
        start_utc = start_local.astimezone(pytz.utc)
        end_local = form.reservation_end.data
        end_utc = end_local.astimezone(pytz.utc)

        # 检查重叠预约
        # 【注意】我们不仅要检查 active/scheduled，还要检查 conflicted，因为 conflicted 随时可能变回 active
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
    """取消预约"""
    reservation = Reservation.query.get_or_404(reservation_id)

    if not current_user.is_admin() and reservation.user_id != current_user.id:
        flash('没有权限执行此操作', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 【优化】允许取消 conflicted 状态的预约
    if reservation.status not in ['scheduled', 'active', 'conflicted']:
        status_cn = {
            'scheduled': '待开始', 'active': '有效', 'conflicted': '冲突',
            'expired': '已作废', 'cancelled': '已取消', 'used': '已使用'
        }.get(reservation.status, reservation.status)
        flash(f'该预约状态为「{status_cn}」，无法取消', 'warning')
        return redirect(url_for('reservations.my_reservations'))

    reservation.status = 'cancelled'
    db.session.commit()

    flash('预约已取消', 'success')
    return redirect(request.referrer or url_for('reservations.my_reservations'))


@bp.route('/use/<int:reservation_id>', methods=['POST'])
@login_required
def use_reservation(reservation_id):
    """使用预约"""
    reservation = Reservation.query.get_or_404(reservation_id)

    if reservation.user_id != current_user.id:
        flash('没有权限使用此预约', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 必须是 active 状态才能使用
    if not reservation.is_active():
        status_cn = {
            'scheduled': '待开始', 'active': '有效', 'conflicted': '冲突',
            'expired': '已作废', 'cancelled': '已取消', 'used': '已使用'
        }.get(reservation.status, reservation.status)
        flash(f'仅「有效且物品可用」的预约可使用，当前状态：{status_cn}', 'warning')
        return redirect(url_for('reservations.my_reservations'))

    reservation.status = 'used'
    db.session.commit()

    flash('预约已转为使用状态，请在借用记录中完成登记', 'success')
    return redirect(url_for('records.create', item_id=reservation.item_id))


@bp.route('/delete/<int:reservation_id>', methods=['POST'])
@login_required
def delete(reservation_id):
    """删除预约"""
    if not current_user.is_admin():
        flash('没有权限执行此操作', 'danger')
        return redirect(url_for('reservations.all_reservations'))

    reservation = Reservation.query.get_or_404(reservation_id)
    item_name = reservation.item.name
    username = reservation.user.username

    db.session.delete(reservation)
    db.session.commit()

    flash(f'成功删除预约记录：物品「{item_name}」（预约人：{username}）', 'success')
    return redirect(url_for('reservations.all_reservations'))