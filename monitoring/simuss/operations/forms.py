import json
import os
from typing import Dict

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from werkzeug.utils import secure_filename
from wtforms import StringField
from wtforms.validators import DataRequired

from . import operation

class OperationUpload(FlaskForm):
  descriptor = FileField('Descriptor', validators=[
    FileRequired(),
    FileAllowed(['yaml', 'json'], 'Only YAML or JSON files are allowed'),])

  def to_descriptor(self) -> Dict:
    return operation.from_file(
      format=os.path.splitext(secure_filename(self.descriptor.data.filename))[-1][1:],
      content=self.descriptor.data.read().decode('utf-8'))
