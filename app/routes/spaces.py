from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Space, Item
from app.forms.space_forms import SpaceForm

bp = Blueprint('spaces', __name__)


# --- 辅助函数：获取空间层级结构 ---
def get_space_hierarchy(parent_id=None, level=0):
    """
    递归获取空间层级结构
    :param parent_id: 父空间ID
    :param level: 当前层级
    :return: list of dict
    """
    spaces = Space.query.filter_by(parent_id=parent_id).all()
    hierarchy = []
    for space in spaces:
        hierarchy.append({
            'space': space,
            'level': level,
            'children': get_space_hierarchy(space.id, level + 1)
        })
    return hierarchy


# --------------------------------

@bp.route('/')
@login_required
def index():
    # 获取顶级空间（parent_id 为空 或 0）
    # 这里假设 parent_id 为 NULL 代表顶级
    spaces = Space.query.filter(Space.parent_id == None).all()

    # 构造数据结构供模板使用
    spaces_data = []
    for space in spaces:
        spaces_data.append({
            'space': space,
            'children': space.children.all()
        })

    return render_template('spaces/index.html', spaces=spaces_data)


@bp.route('/view/<int:id>')
@login_required
def view(id):
    space = Space.query.get_or_404(id)

    # 1. 获取子空间数据
    subspaces_query = space.children.all()
    subspaces_data = []
    for sub in subspaces_query:
        subspaces_data.append({
            'space': sub,
            'children': sub.children.all()
        })

    # 2. 获取物品数据（分页）
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # space.items 是 lazy='dynamic'，可以直接调用 paginate
    pagination = space.items.paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items

    return render_template('spaces/view.html',
                           space=space,
                           subspaces=subspaces_data,
                           items=items,
                           pagination=pagination)


@bp.route('/search/<int:id>', methods=['POST'])
@login_required
def search(id):
    """空间内搜索"""
    space = Space.query.get_or_404(id)
    query = request.form.get('query', '').strip()

    if not query:
        return redirect(url_for('spaces.view', id=id))

    # 搜索逻辑
    items = Item.query.filter(
        Item.space_id == id,
        (Item.name.ilike(f'%{query}%') |
         Item.function.ilike(f'%{query}%') |
         Item.serial_number.ilike(f'%{query}%'))
    ).all()

    return render_template('spaces/search_results.html', space=space, items=items, query=query)


@bp.route('/create/<int:parent_id>', methods=['GET', 'POST'])
@login_required
def create(parent_id):
    if not current_user.is_admin():
        flash('没有权限创建空间')
        return redirect(url_for('spaces.index'))

    # parent_id=0 表示创建顶级空间
    parent = None
    if parent_id != 0:
        parent = Space.query.get_or_404(parent_id)

    form = SpaceForm()
    if form.validate_on_submit():
        space = Space(
            name=form.name.data,
            parent_id=parent_id if parent_id != 0 else None,
            created_by=current_user.id
        )
        db.session.add(space)
        db.session.commit()
        flash(f'空间 "{space.name}" 创建成功')

        if parent:
            return redirect(url_for('spaces.view', id=parent.id))
        return redirect(url_for('spaces.index'))

    return render_template('spaces/edit.html', title='创建空间', form=form, parent=parent)


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('没有权限编辑空间')
        return redirect(url_for('spaces.view', id=id))

    space = Space.query.get_or_404(id)
    form = SpaceForm(obj=space)

    if form.validate_on_submit():
        space.name = form.name.data
        db.session.commit()
        flash(f'空间 "{space.name}" 更新成功')
        if space.parent_id:
            return redirect(url_for('spaces.view', id=space.parent_id))
        return redirect(url_for('spaces.index'))

    return render_template('spaces/edit.html', title='编辑空间', form=form, space=space)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    # 1. 权限检查：只有管理员可以删除空间
    if not current_user.is_admin():
        flash('没有权限删除空间', 'danger')
        return redirect(url_for('spaces.view', id=id))

    space = Space.query.get_or_404(id)
    parent_id = space.parent_id  # 记录父ID以便删除后跳转

    # 2. 安全检查：如果有子空间或物品，禁止删除
    # (虽然前端有 disabled 属性，但后端必须进行二次校验)
    if space.children.count() > 0:
        flash(f'无法删除：该空间包含 {space.children.count()} 个子空间，请先处理子空间。', 'warning')
        return redirect(url_for('spaces.edit', id=id))

    if space.items.count() > 0:
        flash(f'无法删除：该空间包含 {space.items.count()} 个物品，请先移除或转移物品。', 'warning')
        return redirect(url_for('spaces.edit', id=id))

    # 3. 执行删除
    try:
        db.session.delete(space)
        db.session.commit()
        flash(f'空间 "{space.name}" 已成功删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'danger')
        return redirect(url_for('spaces.view', id=id))

    # 4. 删除后跳转逻辑
    # 如果有父空间，返回父空间视图；否则返回顶级空间列表
    if parent_id:
        return redirect(url_for('spaces.view', id=parent_id))
    return redirect(url_for('spaces.index'))