from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import User
from app.utils import admin_required  # 导入修改后的装饰器
from flask_login import current_user

bp = Blueprint('admin', __name__)


# 管理员用户管理页面（查看所有用户）
@bp.route('/user_management')
@login_required
@admin_required  # 基于role字段的权限检查
def user_management():
    # 修改后（按ID升序）
    users = User.query.order_by(User.id.asc()).all()
    return render_template('auth/user_management.html', users=users)


# 切换用户的管理员权限（授予/取消）
@bp.route('/toggle_admin/<int:user_id>')
@login_required
@admin_required
def toggle_admin(user_id):
    # 禁止修改自身权限
    if user_id == current_user.id:
        flash('不能修改自身的管理员权限', 'warning')
        return redirect(url_for('admin.user_management'))

    user = User.query.get_or_404(user_id)
    # 切换role字段：'user'→'admin'，'admin'→'user'
    user.role = 'admin' if user.role == 'user' else 'user'
    db.session.commit()

    action = '授予' if user.role == 'admin' else '取消'
    flash(f'成功{action}用户「{user.username}」的管理员权限', 'success')
    return redirect(url_for('admin.user_management'))


# 【新增】删除用户路由（仅支持POST请求，防止误操作）
@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # 禁止删除自身账号
    if user.id == current_user.id:
        flash('不能删除自身账号', 'warning')
        return redirect(url_for('admin.user_management'))
    # （可选）检查用户是否有未处理的记录/预约，若有则提示
    # 例如：if user.records.count() > 0: flash('请先处理该用户的借用记录', 'danger')...
    db.session.delete(user)
    db.session.commit()
    flash(f'成功删除用户「{user.username}」', 'success')
    return redirect(url_for('admin.user_management'))