from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')


class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators=[
        DataRequired(), Length(min=4, max=64)
    ])
    email = StringField('邮箱', validators=[
        DataRequired(), Email()
    ])
    password = PasswordField('密码', validators=[
        DataRequired(), Length(min=8)
    ])
    password2 = PasswordField('确认密码', validators=[
        DataRequired(), EqualTo('password')
    ])
    submit = SubmitField('注册')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('请使用其他用户名')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('请使用其他邮箱地址')


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    submit = SubmitField('请求密码重置')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('新密码', validators=[
        DataRequired(), Length(min=8)
    ])
    password2 = PasswordField('确认新密码', validators=[
        DataRequired(), EqualTo('password')
    ])
    submit = SubmitField('重置密码')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('旧密码', validators=[DataRequired()])
    new_password = PasswordField('新密码', validators=[
        DataRequired(), Length(min=8)
    ])
    new_password2 = PasswordField('确认新密码', validators=[
        DataRequired(), EqualTo('new_password')
    ])
    submit = SubmitField('修改密码')
