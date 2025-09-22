from flask_wtf import FlaskForm
from wtforms import DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta


class ReservationForm(FlaskForm):
    reservation_start = DateField('预约开始日期', validators=[DataRequired()])
    reservation_end = DateField('预约结束日期', validators=[DataRequired()])
    notes = TextAreaField('预约备注（可选）')
    submit = SubmitField('提交预约')

    def validate_reservation_end(self, reservation_end):
        if self.reservation_start.data and reservation_end.data:
            if reservation_end.data < self.reservation_start.data:
                raise ValidationError('结束日期不能早于开始日期')

            # 限制最长预约时间为30天
            if (reservation_end.data - self.reservation_start.data).days > 30:
                raise ValidationError('预约时间不能超过30天')

            # 不能预约过去的时间
            if self.reservation_start.data < datetime.now().date():
                raise ValidationError('不能预约过去的时间')
