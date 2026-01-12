import atexit
import os
import pytz
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler

# 从 config 导入 config 字典
from config import config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()
migrate = Migrate()

# 全局调度器（避免GC回收）
scheduler = None


def create_app(config_name='default'):
    global scheduler
    app = Flask(__name__)

    # 加载配置（FLASK_CONFIG 对应 config 字典键）
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # 配置日志文件处理器
    log_file = app.config.get('LOG_FILE_PATH')
    if log_file:
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024,
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)  # 新增：确保INFO级别日志输出
        app.logger.info("系统启动：日志文件处理器已配置 (UTF-8)")

    # 注册蓝图
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

    from app.routes.engineer import bp as engineer_bp
    app.register_blueprint(engineer_bp, url_prefix='/engineer')

    # 模板全局函数
    app.jinja_env.globals['get_space_hierarchy'] = get_space_hierarchy

    # 创建数据库表（推送上下文）
    with app.app_context():
        db.create_all()

    # ===================== APScheduler 核心逻辑 =====================
    app.logger.info("="*50)
    app.logger.info("          APScheduler 调试信息开始          ")
    app.logger.info("="*50)
    app.logger.info(f"当前配置环境 (FLASK_CONFIG): {config_name}")
    app.logger.info(f"app.debug 状态: {app.debug}")
    app.logger.info(f"WERKZEUG_RUN_MAIN: {os.environ.get('WERKZEUG_RUN_MAIN')}")
    app.logger.info(f"全局scheduler 初始状态: {scheduler}")
    app.logger.info(f"当前工作目录: {os.getcwd()}")
    app.logger.info(f"tasks.py 存在: {os.path.exists('app/tasks.py')}")

    # 调度器启动条件
    start_scheduler = True
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        start_scheduler = False
        app.logger.warning("调试：开发环境debug模式（非主进程），跳过调度器启动")
    else:
        app.logger.info(f"调试：调度器启动条件 → start_scheduler = {start_scheduler}")

    # 初始化调度器
    if start_scheduler and scheduler is None:
        app.logger.info("调试：进入调度器初始化逻辑")
        try:
            from app.tasks import update_reservation_status, check_overdue_records
            app.logger.info("调试：任务函数导入成功")

            # 初始化调度器（指定时区）
            scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
            app.logger.info("调试：调度器初始化完成")

            # 包装任务函数（推送上下文）
            def wrapped_update_reservation_status():
                app.logger.info("调试：update_reservation_status 任务执行开始")
                with app.app_context():
                    update_reservation_status()
                app.logger.info("调试：update_reservation_status 任务执行完成")

            def wrapped_check_overdue_records():
                app.logger.info("调试：check_overdue_records 任务执行开始")
                with app.app_context():
                    check_overdue_records()
                app.logger.info("调试：check_overdue_records 任务执行完成")

            # 添加任务
            scheduler.add_job(
                func=wrapped_update_reservation_status,
                trigger='interval',
                seconds=30,
                id='update_reservation_status_task',
                replace_existing=True
            )
            app.logger.info("已添加任务：update_reservation_status_task（每30秒）")

            scheduler.add_job(
                func=wrapped_check_overdue_records,
                trigger='interval',
                hours=1,
                id='check_overdue_records_task',
                replace_existing=True
            )
            app.logger.info("已添加任务：check_overdue_records_task（每1小时）")

            # 启动调度器
            scheduler.start()
            app.logger.info("✅ APScheduler 调度器启动成功！")

        except ImportError as e:
            app.logger.error(f"❌ 任务函数导入失败: {str(e)}", exc_info=True)
        except Exception as e:
            app.logger.error(f"❌ 调度器启动失败: {str(e)}", exc_info=True)
    else:
        reason = []
        if not start_scheduler:
            reason.append("start_scheduler=False")
        if scheduler is not None:
            reason.append("scheduler已初始化")
        app.logger.info(f"调试：未启动调度器 → 原因: {', '.join(reason)}")

    # 调度器关闭逻辑
    def shutdown_scheduler():
        app.logger.info("调试：应用退出，执行调度器关闭逻辑")
        if scheduler and scheduler.running:
            scheduler.shutdown()
            app.logger.info("APScheduler 已关闭")
        else:
            app.logger.info("调度器未运行，无需关闭")

    atexit.register(shutdown_scheduler)

    return app


# 导入模型
from app import models