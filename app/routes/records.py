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
    records_query = current_user.records.order_by(Record.start_time.desc())

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

    records_query = Record.query.order_by(Record.start_time.desc())

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
    records = Record.query.filter_by(item_id=item_id).order_by(Record.start_time.desc()).all()
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
        record.return_time = datetime.utcnow()

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
    """删除使用记录（仅管理员）"""
    if not current_user.is_admin():
        flash('没有权限删除记录')
        return redirect(url_for('records.my_records'))

    record = Record.query.get_or_404(record_id)
    item_id = record.item_id

    db.session.delete(record)
    db.session.commit()

    flash('使用记录已删除')
    return redirect(url_for('records.item_records', item_id=item_id))
