import uuid

import flask
import flask_login

from monitoring.monitorlib import scd
from monitoring.monitorlib import fetch
import monitoring.monitorlib.fetch.scd
from monitoring.simuss import db, webapp
from monitoring.simuss.auth import authorization
from . import forms, validate
from .operation import reference_request_from_descriptor


@webapp.route('/operations', methods=['GET', 'POST'])
@flask_login.login_required
def operations():
  form = forms.OperationUpload()
  if flask.request.method == 'POST':
    if form.validate_on_submit():
      try:
        op_descriptor = form.to_descriptor()
      except ValueError as e:
        flask.flash('Error loading Operation descriptor: {}'.format(e), 'error')
        op_descriptor = None
      if op_descriptor is not None:
        parse_errors = validate.scd_operation_descriptor(op_descriptor, 'operation_descriptor')
        if parse_errors:
          for err in parse_errors:
            flask.flash('Error validating Operation descriptor: {}'.format(err), 'error')
        else:
          op_req = reference_request_from_descriptor(op_descriptor)

          # Query the DSS for other Operations
          fetch.scd.operations()

          # Query the DSS for other Constraints

          # Create the

          op_model.id = str(uuid.uuid4())
          return flask.redirect(flask.url_for('operation', id=op_model.id))
    else:
      for err in form.errors:
        flask.flash('Could not validate provided information: {}'.format(err), 'error')
  ops = models.Operation.query
  return flask.render_template('operations.html', title='Operations', form=form, ops=ops)


@webapp.route('/operations/<id>', methods=['GET', 'PUT'])
@flask_login.login_required
def operation(id: str):
  form = forms.OperationUpload()
  op_model = models.Operation.query.filter_by(id=id).first()
  if op_model is None:
    return 'Operation not found', 404
  if flask.request.method == 'GET':
    pass
  elif flask.request.method == 'PUT':
    raise NotImplementedError()
  op = op_model.to_operation()
  return flask.render_template('operation.html', title='Operation', form=form, op=op)


@webapp.route('uss/v1/operations/{id}', methods=['GET'])
@authorization.requires_scope(scd.SCOPE_SC)
def operation_details(id: str):
  op = db.get(db.TABLE_OPERATIONS, id)
  if op is None:
    flask.abort(404, 'Could not find requested Operation')
  return flask.jsonify(op)


@webapp.route('uss/v1/operations/{id}', methods=['GET'])
@authorization.requires_scope(scd.SCOPE_SC)
def operation_notification(id: str):
  try:
    op = flask.request.json
  except ValueError:
    flask.abort(400, 'No JSON body found')
  db.put(db.TABLE_OPERATION_NOTIFICATIONS, id, op)
  return '', 204
