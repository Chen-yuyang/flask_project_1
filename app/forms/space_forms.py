from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class SpaceForm(FlaskForm):
    name = StringField('空间名称', validators=[
        DataRequired(), Length(min=1, max=100)
    ])
    submit = SubmitField('保存')
