from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.forms.record_forms import RecordCreateForm, RecordReturnForm
from app.models import Item, Record, Space, User, Reservation

bp = Blueprint('records', __name__)


@bp.route('/my')
@login_required
def my_records():
    """查看当前用户的使用记录（分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10条

    status = request.args.get('status', '')
    item_name = request.args.get('item_name', '').strip()

    # 基础查询：当前用户的记录
    records_query = current_user.records

    # 筛选：物品名称（模糊查询）
    if item_name:
        records_query = records_query.join(Item).filter(Item.name.ilike(f'%{item_name}%'))

    # 筛选：状态
    if status:
        records_query = records_query.filter(Record.status == status)

    records_query = records_query.order_by(Record._utc_start_time.desc())

    # 使用 paginate 代替 all
    pagination = records_query.paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    return render_template('records/my_records.html', records=records, pagination=pagination)


@bp.route('/all')
@login_required
def all_records():
    """管理员查看所有使用记录（分页）"""
    if not current_user.is_admin():
        flash('没有权限查看所有记录')
        return redirect(url_for('records.my_records'))

    page = request.args.get('page', 1, type=int)
    per_page = 15  # 管理员界面每页显示更多

    # 获取筛选参数
    username = request.args.get('username', '').strip()
    item_name = request.args.get('item_name', '').strip()
    status = request.args.get('status', '')

    records_query = Record.query

    # 联表查询：用户名
    if username:
        records_query = records_query.join(User).filter(User.username.ilike(f'%{username}%'))

    # 联表查询：物品名
    if item_name:
        records_query = records_query.join(Item).filter(Item.name.ilike(f'%{item_name}%'))

    # 筛选：状态
    if status:
        records_query = records_query.filter(Record.status == status)

    records_query = records_query.order_by(Record._utc_start_time.desc())

    # 使用 paginate
    pagination = records_query.paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    return render_template('records/all_records.html', records=records, pagination=pagination)


@bp.route('/item/<int:item_id>')
@login_required
def item_records(item_id):
    """查看特定物品的使用记录（分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = 10

    username = request.args.get('username', '').strip()
    status = request.args.get('status', '')

    item = Item.query.get_or_404(item_id)
    records_query = Record.query.filter_by(item_id=item_id)

    # 筛选：用户名
    if username:
        records_query = records_query.join(User).filter(User.username.ilike(f'%{username}%'))

    # 筛选：状态（虽然通常看物品记录不太需要筛选状态，但保留功能更灵活）
    if status:
        records_query = records_query.filter(Record.status == status)

    records_query = records_query.order_by(Record._utc_start_time.desc())

    pagination = records_query.paginate(page=page, per_page=per_page, error_out=False)
    records = pagination.items

    return render_template('records/item_records.html', records=records, item=item, pagination=pagination)


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    """创建使用记录（借用物品）"""
    item = Item.query.get_or_404(item_id)

    # 【新增】检查是否存在属于当前用户的关联预约（Active 或 Scheduled）
    # 如果是 Active，说明正好是预约时间；如果是 Scheduled，说明是提前来取
    user_reservation = Reservation.query.filter_by(
        item_id=item.id,
        user_id=current_user.id
    ).filter(
        Reservation.status.in_(['active', 'scheduled'])
    ).first()

    # 检查物品状态
    if item.status == 'available':
        # 物品可用，允许借用
        # 但如果有预约（Scheduled状态，提前取货），应该关联处理，否则后面会变成Conflicted
        pass
    elif item.status == 'reserved':
        # 如果是已预约状态，必须拥有有效预约（Active）
        if not user_reservation or user_reservation.status != 'active':
            flash(f'物品 "{item.name}" 已被其他用户预约，当前不可借用。', 'warning')
            return redirect(url_for('items.view', id=item_id))
    else:
        # borrowed 或其他状态
        flash(f'物品 "{item.name}" 当前不可用，状态：{item.status}', 'danger')
        return redirect(url_for('items.view', id=item_id))

    form = RecordCreateForm()
    if form.validate_on_submit():
        # 创建使用记录
        record = Record(
            item_id=item_id,
            user_id=current_user.id,
            space_path=item.space.get_path(),
            usage_location=form.usage_location.data,
            status='using'
        )

        # 更新物品状态
        item.status = 'borrowed'

        # 【新增】消耗预约：如果存在有效或待开始的预约，将其状态更新为 used
        if user_reservation:
            user_reservation.status = 'used'

        db.session.add(record)
        db.session.commit()

        flash(f'成功借用物品 "{item.name}"', 'success')
        return redirect(url_for('items.view', id=item_id))

    return render_template('records/create.html', form=form, item=item)


@bp.route('/return/<int:record_id>', methods=['GET', 'POST'])
@login_required
def return_item(record_id):
    """归还物品"""
    record = Record.query.get_or_404(record_id)

    # 检查权限
    if not current_user.is_admin() and record.user_id != current_user.id:
        flash('没有权限执行此操作')
        return redirect(url_for('items.view', id=record.item_id))

    # 检查记录状态
    if record.status != 'using':
        flash('该物品已归还')
        return redirect(url_for('items.view', id=record.item_id))

    form = RecordReturnForm()
    if form.validate_on_submit() or request.method == 'POST':
        # 更新记录状态
        record.status = 'returned'
        record._utc_return_time = datetime.utcnow()

        # 更新物品状态
        item = record.item
        item.status = 'available'

        db.session.commit()

        flash(f'成功归还物品 "{item.name}"')
        return redirect(url_for('items.view', id=item.id))

    return render_template('records/return.html', form=form, record=record)


@bp.route('/delete/<int:record_id>', methods=['POST'])
@login_required
def delete(record_id):
    """删除使用记录（仅管理员），删除后返回“所有记录”页面并保留筛选状态"""
    # 1. 权限检查：仅管理员可执行
    if not current_user.is_admin():
        flash('没有权限删除使用记录', 'danger')
        return redirect(
            url_for('records.all_records', status=request.args.get('status'), page=request.args.get('page')))

    # 2. 查询要删除的记录
    record = Record.query.get_or_404(record_id)

    # 3. 记录删除信息（用于日志或提示，可选）
    item_name = record.item.name

    # 4. 执行删除操作
    db.session.delete(record)
    db.session.commit()

    flash(f'成功删除物品「{item_name}」的使用记录', 'success')

    # 关键改动：重定向到“所有记录”页面，并将当前的筛选状态传递回去
    return redirect(url_for(
        'records.all_records',
        status=request.args.get('status'),
        username=request.args.get('username'),
        item_name=request.args.get('item_name'),
        page=request.args.get('page')
    ))