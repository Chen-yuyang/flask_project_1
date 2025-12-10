from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models import Item, Record, Space
from app.forms.record_forms import RecordCreateForm, RecordReturnForm

bp = Blueprint('records', __name__)


@bp.route('/my')
@login_required
def my_records():
    """查看当前用户的使用记录"""
    status = request.args.get('status', '')
    records_query = current_user.records.order_by(Record._utc_start_time.desc())

    if status:
        records_query = records_query.filter(Record.status == status)

    records = records_query.all()
    return render_template('records/my_records.html', records=records)


@bp.route('/all')
@login_required
def all_records():
    """管理员查看所有使用记录"""
    if not current_user.is_admin():
        flash('没有权限查看所有记录')
        return redirect(url_for('records.my_records'))

    user_id = request.args.get('user_id', '')
    item_id = request.args.get('item_id', '')
    status = request.args.get('status', '')

    records_query = Record.query.order_by(Record._utc_start_time.desc())

    if user_id:
        records_query = records_query.filter(Record.user_id == user_id)
    if item_id:
        records_query = records_query.filter(Record.item_id == item_id)
    if status:
        records_query = records_query.filter(Record.status == status)

    records = records_query.all()
    return render_template('records/all_records.html', records=records)


@bp.route('/item/<int:item_id>')
@login_required
def item_records(item_id):
    """查看特定物品的使用记录"""
    item = Item.query.get_or_404(item_id)
    records = Record.query.filter_by(item_id=item_id).order_by(Record._utc_start_time.desc()).all()
    return render_template('records/item_records.html', records=records, item=item)


@bp.route('/create/<int:item_id>', methods=['GET', 'POST'])
@login_required
def create(item_id):
    """创建使用记录（借用物品）"""
    item = Item.query.get_or_404(item_id)

    # 检查物品状态
    if item.status != 'available':
        flash(f'物品 "{item.name}" 当前不可用，状态：{item.status}')
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

        db.session.add(record)
        db.session.commit()

        flash(f'成功借用物品 "{item.name}"')
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
        # 无权限时，同样返回“所有记录”页面，并携带原筛选参数
        return redirect(url_for(
            'records.all_records',
            status=request.args.get('status')
        ))

    # 2. 查询要删除的记录
    record = Record.query.get_or_404(record_id)

    # 3. 记录删除信息（用于日志或提示，可选）
    item_name = record.item.name
    user_username = record.user.username

    # 4. 执行删除操作
    db.session.delete(record)
    db.session.commit()

    # 5. 记录操作日志（可选，但推荐）
    # current_app.logger.info(
    #     f"管理员 {current_user.username} 删除了使用记录: "
    #     f"物品[{item_name}], 使用人[{user_username}]"
    # )

    # 6. 发送成功提示并跳转
    flash(f'成功删除物品「{item_name}」的使用记录', 'success')

    # 关键改动：重定向到“所有记录”页面，并将当前的筛选状态（status）传递回去
    return redirect(url_for(
        'records.all_records',
        status=request.args.get('status')  # 保留原筛选状态
    ))
