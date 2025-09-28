from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import urlsplit  # 将url_parse改为urlsplit
from app import db
from app.models import User
from app.forms.auth_forms import (
    LoginForm, RegistrationForm, ResetPasswordRequestForm,
    ResetPasswordForm, ChangePasswordForm
)
from app.email import send_password_reset_email

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('无效的用户名或密码')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        # 使用urlsplit替代原来的url_parse
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)

    return render_template('auth/login.html', title='登录', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # 1. 定义管理员专属注册邮箱
        ADMIN_REGISTER_EMAIL = "1055912570@qq.com"

        # 2. 校验：该邮箱是否已注册（避免重复创建管理员）
        existing_user = User.query.filter_by(
            email=form.email.data
        ).first()
        if existing_user:
            flash(f'邮箱「{form.email.data}」已被注册，请更换其他邮箱', 'danger')
            return redirect(url_for('auth.register'))

        # 3. 校验：该邮箱是否已注册为管理员（双重保险）
        existing_admin = User.query.filter_by(
            email=ADMIN_REGISTER_EMAIL,
            role='admin'
        ).first()
        if form.email.data == ADMIN_REGISTER_EMAIL and existing_admin:
            flash(f'管理员邮箱「{ADMIN_REGISTER_EMAIL}」已注册，无需重复创建', 'warning')
            return redirect(url_for('auth.login'))

        # 4. 创建用户实例：根据邮箱动态设置角色
        user = User(
            username=form.username.data,
            email=form.email.data,
            # 核心逻辑：匹配指定邮箱则设为admin，否则默认user
            role='admin' if form.email.data == ADMIN_REGISTER_EMAIL else 'user'
        )

        # 5. 加密密码并提交数据库
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            # 6. 差异化提示信息
            if user.is_admin():
                flash(f'🎉 管理员账号注册成功！用户名：{user.username}', 'success')
            else:
                flash(f'✅ 普通用户注册成功！用户名：{user.username}', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ 注册失败：{str(e)}', 'danger')

    return render_template('auth/register.html', title='注册', form=form)


@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('请检查您的邮箱，获取密码重置链接')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html',
                           title='重置密码', form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('您的密码已重置')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('旧密码不正确')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('您的密码已更新')
        return redirect(url_for('main.index'))

    return render_template('auth/change_password.html', form=form)
