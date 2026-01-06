import atexit
import os
import pytz

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
# 导入APScheduler
from apscheduler.schedulers.background import BackgroundScheduler

# 【修改点1】：从 config 导入 config 字典，以支持环境切换
from config import config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()
migrate = Migrate()


def create_app(config_name='default'):
    app = Flask(__name__)

    # 【修改点2】：使用 config 字典加载配置，而不是直接加载类
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # SSL 重定向处理 (适配 config.py 中的配置)
    # if app.config.get('SSL_REDIRECT'):
    #     from flask_sslify import SSLify
    #     sslify = SSLify(app)

    # -------------------- 蓝图注册 (保留你原有的导入方式) --------------------

    # 延迟导入路由，避免循环导入
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.spaces import bp as spaces_bp, get_space_hierarchy
    app.register_blueprint(spaces_bp, url_prefix='/spaces')

    from app.routes.items import bp as items_bp
    app.register_blueprint(items_bp, url_prefix='/items')

    from app.routes.records import bp as records_bp
    app.register_blueprint(records_bp, url_prefix='/records')

    from app.routes.reservations import bp as reservations_bp
    app.register_blueprint(reservations_bp, url_prefix='/reservations')

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 将空间层级函数注册为模板全局函数
    app.jinja_env.globals['get_space_hierarchy'] = get_space_hierarchy

    # 创建数据库表
    # 【修正】：取消注释以确保表被创建。db.create_all() 会检查表是否存在，不存在则创建。
    with app.app_context():
        db.create_all()

    # =====================================================================
    # APScheduler 定时任务配置 (保留你的完整逻辑)
    # =====================================================================
    scheduler = None

    # 仅在非调试模式或主进程中启动调度器
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            # 延迟导入任务函数
            from app.tasks import update_reservation_status, check_overdue_records

            scheduler = BackgroundScheduler()

            # 任务1: 更新预约状态 (每30秒一次)
            scheduler.add_job(
                func=update_reservation_status,
                args=[app.app_context()],
                trigger='interval',
                seconds=30,
                id='update_reservation_status_task',
                replace_existing=True,
            )
            app.logger.info("已添加任务: update_reservation_status_task")

            # 任务2: 逾期记录检查 (每1小时一次)
            scheduler.add_job(
                func=check_overdue_records,
                args=[app.app_context()],
                trigger='interval',
                hours=1,
                id='check_overdue_records_task',
                replace_existing=True,
            )
            app.logger.info("已添加任务: check_overdue_records_task")

            # 启动调度器
            try:
                scheduler.start()
                app.logger.info("APScheduler 调度器已启动。")
            except Exception as e:
                app.logger.error(f"启动 APScheduler 失败: {e}")

        except ImportError as e:
            app.logger.warning(f"定时任务导入失败，调度器未启动: {e}")

    # -------------------- 统一的关闭逻辑 --------------------
    def shutdown_scheduler():
        if scheduler and scheduler.running:
            app.logger.info("应用正在退出，关闭 APScheduler...")
            scheduler.shutdown()
            app.logger.info("APScheduler 已关闭。")

    atexit.register(shutdown_scheduler)
    # =====================================================================

    return app


# 导入模型 (保留)
from app import models