import pytz

from flask_wtf import FlaskForm
from wtforms import DateField, TextAreaField, SubmitField
from wtforms.fields.datetime import DateTimeField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta

LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')  # 与模型一致的时区


class ReservationForm(FlaskForm):
    reservation_start = DateTimeField(
        '预约开始时间',
        format='%Y-%m-%dT%H:%M:%S',  # 匹配前端 datetime-local 格式
        validators=[DataRequired('请选择开始时间')],
        default=lambda: datetime.now(LOCAL_TIMEZONE).replace(microsecond=0)  # 默认带时区
    )
    reservation_end = DateTimeField(
        '预约结束时间',
        format='%Y-%m-%dT%H:%M:%S',
        validators=[DataRequired('请选择结束时间')],
        default=lambda: (datetime.now(LOCAL_TIMEZONE) + timedelta(hours=1)).replace(microsecond=0)  # 默认带时区
    )
    notes = TextAreaField('预约备注（可选）')
    submit = SubmitField('提交预约')

    def validate_reservation_end(self, reservation_end):
        if self.reservation_start.data and reservation_end.data:
            # 关键修复1：将表单获取的 naive 时间转换为带本地时区的 aware 时间
            # （前端传递的时间是本地时间，但默认是 naive，需手动添加时区）
            start_aware = LOCAL_TIMEZONE.localize(self.reservation_start.data)
            end_aware = LOCAL_TIMEZONE.localize(reservation_end.data)
            current_time = datetime.now(LOCAL_TIMEZONE).replace(microsecond=0)  # 带时区的当前时间

            # 1. 结束时间不能早于开始时间（均为 aware 时间）
            if end_aware < start_aware:
                raise ValidationError('结束时间不能早于开始时间')

            # 2. 限制最长预约时间为7天（均为 aware 时间）
            max_duration = timedelta(days=7)
            if (end_aware - start_aware) > max_duration:
                raise ValidationError('预约时间不能超过7天')

            # 3. 不能预约过去的时间（均为 aware 时间）
            if start_aware < current_time:
                raise ValidationError('不能预约过去的时间')
