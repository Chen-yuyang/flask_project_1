from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models import Item, Space, Record, Reservation
from app.forms.item_forms import ItemForm

from app.utils import generate_and_save_item_qrcode  # 导入工具函数


bp = Blueprint('items', __name__)


@bp.route('/')
@login_required
def all_items():
    query = request.args.get('query', '')
    status = request.args.get('status', '')

    items_query = Item.query

    # 应用搜索条件
    if query:
        items_query = items_query.filter(
            (Item.name.ilike(f'%{query}%') |
             Item.function.ilike(f'%{query}%') |
             Item.serial_number.ilike(f'%{query}%'))
        )

    # 应用状态筛选
    if status:
        items_query = items_query.filter(Item.status == status)

    items = items_query.all()
    return render_template('items/all_items.html', items=items)


@bp.route('/<int:id>')
@login_required
def view(id):
    item = Item.query.get_or_404(id)

    # 获取当前借用记录（如果有）
    current_record = Record.query.filter_by(
        item_id=id,
        status='using'
    ).first()

    # 获取最近的使用记录
    recent_records = Record.query.filter_by(item_id=id).order_by(Record._utc_start_time.desc()).limit(5).all()

    # 获取当前有效的预约
    active_reservations = Reservation.query.filter_by(
        item_id=id,
        status='valid'
    ).filter(
        Reservation._utc_reservation_start <= datetime.utcnow(),
        Reservation._utc_reservation_end >= datetime.utcnow()
    ).all()

    return render_template('items/view.html',
                           item=item,
                           current_record=current_record,
                           recent_records=recent_records,
                           active_reservations=active_reservations)


@bp.route('/create/<int:space_id>', methods=['GET', 'POST'])
@login_required
def create(space_id):
    # 只有管理员可以创建物品
    if not current_user.is_admin():
        flash('没有权限创建物品')
        return redirect(url_for('spaces.view', id=space_id))

    space = Space.query.get_or_404(space_id)
    form = ItemForm()
    form.space_id.data = space_id

    if form.validate_on_submit():
        item = Item(
            name=form.name.data,
            serial_number=form.serial_number.data,
            function=form.function.data,
            status='available',
            space_id=space_id,
            created_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()  # 首次提交：获取item.id（自增主键）

        # 生成并保存二维码（关键新增代码）
        qr_path = generate_and_save_item_qrcode(item.id)  # 生成二维码
        item.barcode_path = qr_path  # 保存路径到物品记录
        db.session.commit()  # 二次提交：保存二维码路径

        flash(f'物品 "{item.name}" 创建成功，二维码已生成')
        return redirect(url_for('spaces.view', id=space_id))

    return render_template('items/edit.html',
                           title='创建物品',
                           form=form,
                           space=space)


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    # 只有管理员可以编辑物品
    if not current_user.is_admin():
        flash('没有权限编辑物品')
        return redirect(url_for('items.view', id=id))

    item = Item.query.get_or_404(id)
    form = ItemForm(item_id=id, obj=item)

    if form.validate_on_submit():
        item.name = form.name.data
        item.serial_number = form.serial_number.data
        item.function = form.function.data
        item.status = form.status.data
        item.space_id = form.space_id.data
        db.session.commit()
        flash(f'物品 "{item.name}" 更新成功')
        return redirect(url_for('items.view', id=id))

    return render_template('items/edit.html',
                           title='编辑物品',
                           form=form,
                           item=item)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    # 只有管理员可以删除物品
    if not current_user.is_admin():
        flash('没有权限删除物品')
        return redirect(url_for('items.view', id=id))

    item = Item.query.get_or_404(id)
    space_id = item.space_id

    db.session.delete(item)
    db.session.commit()
    flash(f'物品 "{item.name}" 已删除')
    return redirect(url_for('spaces.view', id=space_id))
