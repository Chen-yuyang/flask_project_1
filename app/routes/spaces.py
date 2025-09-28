from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import Space, Item
from app.forms.space_forms import SpaceForm

# 创建蓝图
bp = Blueprint('spaces', __name__)


def get_space_hierarchy(parent_id=None):
    """
    递归获取空间层级结构

    参数:
        parent_id: 父空间ID，为None时获取顶级空间

    返回:
        层级结构列表，每个元素为字典:
        {
            'space': 空间对象,
            'children': 子空间层级结构列表
        }
    """
    # 查询指定父空间下的所有子空间，并按名称排序
    spaces = Space.query.filter_by(parent_id=parent_id) \
        .order_by(Space.name) \
        .all()

    hierarchy = []
    for space in spaces:
        # 递归获取子空间
        children = get_space_hierarchy(space.id)
        hierarchy.append({
            'space': space,
            'children': children
        })
    return hierarchy


@bp.route('/')
@login_required
def index():
    """显示所有顶级空间"""
    # 获取顶级空间（无父空间的空间）
    top_spaces = get_space_hierarchy()
    return render_template('spaces/index.html',
                           title='空间管理',
                           spaces=top_spaces)


@bp.route('/view/<int:id>')
@login_required
def view(id):
    """查看指定空间的详情，包括其子空间和物品"""
    space = Space.query.get_or_404(id)
    # 获取当前空间的子空间
    subspaces = get_space_hierarchy(id)
    # 获取当前空间的物品
    items = Item.query.filter_by(space_id=id).all()
    return render_template('spaces/view.html',
                           title=space.name,
                           space=space,
                           subspaces=subspaces,
                           items=items)


@bp.route('/create/<int:parent_id>', methods=['GET', 'POST'])
@login_required
def create(parent_id):
    """创建新空间，可指定父空间"""
    # 权限检查：只有管理员可以创建空间
    if not current_user.is_admin():
        flash('没有权限创建空间', 'danger')
        return redirect(url_for('spaces.index'))

    parent = None
    if parent_id != 0:
        parent = Space.query.get_or_404(parent_id)

    form = SpaceForm()
    if form.validate_on_submit():
        # 创建新空间
        space = Space(
            name=form.name.data,
            parent_id=parent_id if parent_id != 0 else None,
            created_by=current_user.id
        )
        db.session.add(space)
        try:
            db.session.commit()
            flash(f'空间 "{space.name}" 创建成功', 'success')

            # 根据是否有父空间决定跳转方向
            if parent:
                return redirect(url_for('spaces.view', id=parent_id))
            return redirect(url_for('spaces.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建空间失败: {str(e)}', 'danger')

    return render_template('spaces/edit.html',
                           title='创建空间',
                           form=form,
                           parent=parent)


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑现有空间"""
    # 权限检查：只有管理员可以编辑空间
    if not current_user.is_admin():
        flash('没有权限编辑空间', 'danger')
        return redirect(url_for('spaces.view', id=id))

    space = Space.query.get_or_404(id)
    form = SpaceForm(obj=space)

    if form.validate_on_submit():
        try:
            space.name = form.name.data
            db.session.commit()
            flash(f'空间 "{space.name}" 更新成功', 'success')
            return redirect(url_for('spaces.view', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'更新空间失败: {str(e)}', 'danger')

    return render_template('spaces/edit.html',
                           title='编辑空间',
                           form=form,
                           space=space,
                           parent=space.parent)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除指定空间"""
    # 权限检查：只有管理员可以删除空间
    if not current_user.is_admin():
        flash('没有权限删除空间', 'danger')
        return redirect(url_for('spaces.view', id=id))

    space = Space.query.get_or_404(id)
    parent_id = space.parent_id if space.parent else 0
    space_name = space.name  # 保存空间名称用于提示信息

    # 检查是否有子空间
    if space.children.count() > 0:
        flash('无法删除含有子空间的空间，请先删除子空间', 'warning')
        return redirect(url_for('spaces.view', id=id))

    # 检查是否有物品
    if space.items.count() > 0:
        flash('无法删除含有物品的空间，请先移除或转移物品', 'warning')
        return redirect(url_for('spaces.view', id=id))

    try:
        db.session.delete(space)
        db.session.commit()
        flash(f'空间 "{space_name}" 已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除空间失败: {str(e)}', 'danger')

    # 根据是否有父空间决定跳转方向
    if parent_id:
        return redirect(url_for('spaces.view', id=parent_id))
    return redirect(url_for('spaces.index'))


@bp.route('/<int:id>/search', methods=['GET', 'POST'])
@login_required
def search(id):
    """在指定空间内搜索物品"""
    space = Space.query.get_or_404(id)

    # 从GET或POST请求中获取查询参数
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
    else:
        query = request.args.get('query', '').strip()

    # 根据查询条件过滤物品
    if query:
        items = Item.query.filter(
            Item.space_id == id,
            (Item.name.ilike(f'%{query}%') |
             Item.function.ilike(f'%{query}%') |
             Item.serial_number.ilike(f'%{query}%'))
        ).all()
    else:
        # 如果没有查询条件，返回所有物品
        items = Item.query.filter_by(space_id=id).all()

    return render_template('spaces/search_results.html',
                           title=f'在 {space.name} 中搜索',
                           space=space,
                           items=items,
                           query=query)
