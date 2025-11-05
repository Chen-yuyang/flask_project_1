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
        format='%Y-%m-%dT%H:%M',  # 匹配datetime-local的“年-月-日T时:分”格式
        validators=[DataRequired('请选择开始时间')],
        default=lambda: datetime.now(LOCAL_TIMEZONE).replace(second=0, microsecond=0)
    )
    reservation_end = DateTimeField(
        '预约结束时间',
        format='%Y-%m-%dT%H:%M',  # 同样匹配到“时:分”
        validators=[DataRequired('请选择结束时间')],
        default=lambda: (datetime.now(LOCAL_TIMEZONE) + timedelta(hours=1)).replace(second=0, microsecond=0)
    )
    notes = TextAreaField('预约备注（可选）')
    submit = SubmitField('提交预约')

    # 验证逻辑保持不变（时区统一为东八区）
    def validate_reservation_end(self, reservation_end):
        if self.reservation_start.data and reservation_end.data:
            start_aware = LOCAL_TIMEZONE.localize(self.reservation_start.data)
            end_aware = LOCAL_TIMEZONE.localize(reservation_end.data)
            current_time = datetime.now(LOCAL_TIMEZONE).replace(second=0, microsecond=0)

            if end_aware < start_aware:
                raise ValidationError('结束时间不能早于开始时间')
            if (end_aware - start_aware) > timedelta(days=7):
                raise ValidationError('预约时间不能超过7天')
            if start_aware < current_time:
                raise ValidationError('不能预约过去的时间')
