import pytz
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_, case, desc

from app import db
from app.models import Item, Reservation, Record
from app.forms.reservation_forms import ReservationForm
from app.email import send_email

bp = Blueprint('reservations', __name__)
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')


@bp.route('/my')
@login_required
def my_reservations():
    """查看当前用户的预约（支持状态和物品筛选，按最近预约排序）"""
    # 获取筛选参数
    status = request.args.get('status', '')
    item_id = request.args.get('item_id', '')

    # 构建查询：当前用户的预约
    reservations_query = current_user.reservations

    # 状态筛选
    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)

    # 物品筛选
    if item_id:
        reservations_query = reservations_query.filter(Reservation.item_id == item_id)

    # 关键改动：使用数据库原始列 _utc_reservation_start 进行倒序排序
    # （替换为你模型中实际存储预约时间的列名）
    reservations_query = reservations_query.order_by(Reservation._utc_reservation_start.desc())

    reservations = reservations_query.all()
    now_local = datetime.now(LOCAL_TIMEZONE)

    return render_template('reservations/my_reservations.html',
                           reservations=reservations,
                           now_local=now_local,
                           current_status=status,
                           current_item_id=item_id
                           )


# 确保导入了 User 模型
from app.models import Reservation, Item, User  # <-- 在这里添加 User


@bp.route('/all')
@login_required
def all_reservations():
    """查看所有预约（仅管理员）"""
    if not current_user.is_admin():
        flash('没有权限查看所有预约记录', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    # 获取筛选参数
    status = request.args.get('status', '')
    item_id = request.args.get('item_id', '')
    user_id = request.args.get('user_id', '')

    # 构建查询，并按预约开始时间倒序排序（最近的在前面）
    reservations_query = Reservation.query.order_by(Reservation._utc_reservation_start.desc())

    # 应用筛选条件
    if status in ['scheduled', 'active', 'expired', 'cancelled', 'used', 'conflicted']:
        reservations_query = reservations_query.filter(Reservation.status == status)
    if item_id:
        reservations_query = reservations_query.filter(Reservation.item_id == item_id)
    if user_id:
        reservations_query = reservations_query.filter(Reservation.user_id == user_id)

    # 执行查询
    reservations = reservations_query.all()
    all_items = Item.query.all()

    # ==================== 关键改动 ====================
    # 查询所有用户，用于在模板的下拉框中显示
    all_users = User.query.all()
    # ==================================================

    # 渲染模板，并将 all_users 传递过去
    return render_template(
        'reservations/all_reservations.html',
        reservations=reservations,
        all_items=all_items,
        all_users=all_users,  # <-- 将用户列表传递给模板
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
    # update_reservation_status()

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