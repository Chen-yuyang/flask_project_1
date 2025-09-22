import os
from datetime import timedelta


class Config:
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///item_management.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    # 邮件配置
    MAIL_SERVER = 'smtp.qq.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = '1055912570@qq.com'
    MAIL_PASSWORD = 'xkuqxilmgrypbdif'
    MAIL_DEFAULT_SENDER = '1055912570@qq.com'

    # 会话配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # 分页配置
    ITEMS_PER_PAGE = 10
    RECORDS_PER_PAGE = 10