import os
from dotenv import load_dotenv
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

# 尝试加载 .env 文件
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'

    # 邮件配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # 【保留你的自定义配置】：邮件主题与发件人格式
    FLASKY_MAIL_SUBJECT_PREFIX = '[Item Management]'  # 英文前缀用于日志
    MAIL_SUBJECT_PREFIX = '[物品管理系统]'  # 中文前缀用于实际邮件

    # 自动构建发件人格式
    FLASKY_MAIL_SENDER = os.environ.get('FLASKY_MAIL_SENDER') or 'Admin <{}>'.format(MAIL_USERNAME)
    MAIL_SENDER = f'ItemSystem <{MAIL_USERNAME}>' if MAIL_USERNAME else 'ItemSystem'

    # 超级管理员配置
    FLASKY_ADMIN = os.environ.get('FLASKY_ADMIN')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    FLASKY_POSTS_PER_PAGE = 20
    FLASKY_SLOW_DB_QUERY_TIME = 0.5
    SSL_REDIRECT = False

    # 【保留你的自定义配置】：会话与分页
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    ITEMS_PER_PAGE = 10
    RECORDS_PER_PAGE = 10
    BABEL_DEFAULT_TIMEZONE = 'Asia/Shanghai'

    # 【保留你的自定义配置】：二维码基础链接
    QR_CODE_BASE_URL = os.environ.get('QR_CODE_BASE_URL') or 'http://192.168.1.101:8080'

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    # 【核心修复】：指向 instance/item_management.db，解决 no such table 问题
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'instance', 'item_management.db')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'sqlite://'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    # 【核心修复】：生产环境同样指向正确的 instance 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'instance', 'item_management.db')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

        # 生产环境错误日志发送邮件给管理员
        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, 'MAIL_USERNAME', None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, 'MAIL_USE_TLS', None):
                secure = ()

        if cls.MAIL_SERVER and cls.FLASKY_ADMIN:
            mail_handler = SMTPHandler(
                mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
                fromaddr=cls.FLASKY_MAIL_SENDER,
                toaddrs=[cls.FLASKY_ADMIN],
                subject=cls.FLASKY_MAIL_SUBJECT_PREFIX + ' Application Error',
                credentials=credentials,
                secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)


class DockerConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,

    'default': DevelopmentConfig
}