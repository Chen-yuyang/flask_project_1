from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length


class RecordCreateForm(FlaskForm):
    usage_location = StringField('使用地点', validators=[
        DataRequired(), Length(min=1, max=255)
    ])
    notes = TextAreaField('备注（可选）')
    submit = SubmitField('确认使用')


class RecordReturnForm(FlaskForm):
    notes = TextAreaField('归还备注（可选）')
    submit = SubmitField('确认归还')
