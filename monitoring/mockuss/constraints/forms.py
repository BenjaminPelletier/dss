import json
import os
from typing import Dict

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from werkzeug.utils import secure_filename
from wtforms import StringField, HiddenField
from wtforms.validators import DataRequired

from . import constraint


class ConstraintUpload(FlaskForm):
  verb = HiddenField()
  descriptor = FileField('Descriptor', validators=[
    FileRequired(),
    FileAllowed(['yaml', 'json'], 'Only YAML or JSON files are allowed'),])

  def to_descriptor(self) -> constraint.Descriptor:
    return constraint.Descriptor.from_file(
      format=os.path.splitext(secure_filename(self.descriptor.data.filename))[-1][1:],
      content=self.descriptor.data.read().decode('utf-8'))

  def get_id(self) -> str:
    return self.id.data

  @property
  def verb_value(self) -> str:
    return self.verb.data
