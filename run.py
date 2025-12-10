import click
from app import create_app, db
from app.models import Record
from app.email import send_overdue_reminder

app = create_app()


@app.cli.command("init-db")
def init_db():
    """初始化数据库"""
    db.drop_all()
    db.create_all()
    click.echo('数据库已初始化')


@app.cli.command("check-overdue")
def manual_check_overdue():
    """手动检查逾期记录（保留手动触发的功能）"""
    with app.app_context():
        from datetime import datetime, timedelta
        overdue_records = Record.query.filter(
            Record.status == 'using',
            Record.start_time < datetime.utcnow() - timedelta(days=10)
        ).all()

        for record in overdue_records:
            send_overdue_reminder(record)
    click.echo('已检查逾期记录并发送提醒')


if __name__ == '__main__':
    # 移除原来的Timer启动逻辑（由APScheduler统一管理定时任务）
    app.run(host="0.0.0.0", port=5000, debug=True)  # debug=True仅用于开发
