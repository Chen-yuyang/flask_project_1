from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import Item, Record, Reservation, Space
from app.routes.spaces import get_space_hierarchy

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if current_user.is_authenticated:
        # 获取最近的使用记录
        recent_records = current_user.records.order_by(Record.start_time.desc()).limit(5).all()

        # 获取当前用户的有效预约
        my_reservations = current_user.reservations.filter(
            Reservation.status == 'valid',
            Reservation.reservation_end >= datetime.utcnow()
        ).order_by(Reservation.reservation_start).limit(5).all()

        return render_template('main/index.html',
                               recent_records=recent_records,
                               my_reservations=my_reservations)
    return render_template('main/index.html')


@bp.route('/search')
@login_required
def global_search():
    query = request.args.get('query', '')
    results = {
        'items': [],
        'records': [],
        'spaces': []
    }

    if query:
        # 搜索物品
        results['items'] = Item.query.filter(
            (Item.name.ilike(f'%{query}%') |
             Item.function.ilike(f'%{query}%') |
             Item.serial_number.ilike(f'%{query}%'))
        ).all()

        # 搜索记录
        results['records'] = Record.query.filter(
            (Record.usage_location.ilike(f'%{query}%') |
             Record.space_path.ilike(f'%{query}%'))
        ).all()

        # 搜索空间
        results['spaces'] = Space.query.filter(
            Space.name.ilike(f'%{query}%')
        ).all()

    total_results = len(results['items']) + len(results['records']) + len(results['spaces'])

    return render_template('main/search_results.html',
                           query=query,
                           results=results,
                           total_results=total_results)
