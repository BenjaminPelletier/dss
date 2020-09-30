import datetime
import uuid

import flask
import flask_login

from monitoring.monitorlib import scd
from monitoring.monitorlib import fetch
import monitoring.monitorlib.fetch.scd
import monitoring.monitorlib.mutate.scd
from monitoring.mockuss import db, utm_client, webapp, config
from monitoring.mockuss.auth import authorization
from . import constraint, forms


@webapp.route('/constraints/<id>', methods=['GET', 'POST'])
@flask_login.login_required
def constraint_route(id: str):
  try:
    id_uuid = uuid.UUID(id)
  except ValueError:
    flask.abort(400, 'ID {} is not in UUID format'.format(id))
  if id_uuid.version != 4:
    flask.abort(400, 'ID is a UUID version {}; expected version 4'.format(id_uuid.version))

  dss_ref = fetch.scd.constraint_reference(utm_client, id)

  uss_constraint = None
  constraint_ref = None
  form = forms.ConstraintUpload()

  if flask.request.method == 'GET':
    raw = db.get(db.TABLE_CONSTRAINTS, id)
    uss_constraint = constraint.Owned(raw) if raw else None
    if uss_constraint and not dss_ref.success:
      # USS thought there was a Constraint in the system, but it wasn't in DSS
      db.delete(db.TABLE_CONSTRAINTS, id)
      uss_constraint = None
    if dss_ref.success and not uss_constraint:
      # Constraint exists, but it is not in the USS database
      constraint_ref = dss_ref

  elif flask.request.method == 'POST' and form.verb_value == 'PUT':
    if form.validate_on_submit():
      try:
        constraint_descriptor = form.to_descriptor()
        if not constraint_descriptor.valid:
          flask.flash('Constraint descriptor was not valid')
          constraint_descriptor = None
      except ValueError as e:
        flask.flash('Error loading Constraint descriptor: {}'.format(e), 'error')
        constraint_descriptor = None
      if constraint_descriptor is not None:
        if dss_ref.success or dss_ref.missing:
          # Ok to create or update Constraint
          details = constraint_descriptor.to_details(datetime.datetime.utcnow())
          old_version = dss_ref.reference['version'] if not dss_ref.missing else 0
          base_url = webapp.config[config.KEY_BASE_URL]
          put_result = monitoring.monitorlib.mutate.scd.put_constraint(utm_client, details, base_url, id, old_version)
          uss_constraint = constraint.Owned.from_mutation(put_result, details)
          db.put(db.TABLE_CONSTRAINTS, id, uss_constraint)
        else:
          flask.flash('Error querying Constraint {} from DSS: {}'.format(id, dss_ref.error))

  elif flask.request.method == 'POST' and form.verb_value == 'DELETE':
    if not dss_ref.success:
      flask.flash('Error reading Constraint reference from DSS: {}'.format(dss_ref.error))
      return flask.redirect(flask.url_for('constraint_route', id=id), code=303)
    delete_result = monitoring.monitorlib.mutate.scd.delete_constraint(utm_client, id)
    if delete_result.ref_result.success:
      return flask.redirect(flask.url_for('constraint_route', id=id), code=303)

  return flask.render_template(
    'constraint.html', title='Constraint {}'.format(id), constraint_id=id,
    form=form, constraint=uss_constraint, constraint_ref=constraint_ref)


# @webapp.route('/constraints')
# @flask_login.login_required
# def constraints():
#   form = forms.ConstraintUpload()
#   if flask.request.method == 'POST':
#     if form.validate_on_submit():
#       try:
#         constraint_descriptor = form.to_descriptor()
#         if not constraint_descriptor.valid:
#           raise ValueError('Constraint descriptor was not valid')
#       except ValueError as e:
#         flask.flash('Error loading Constraint descriptor: {}'.format(e), 'error')
#         constraint_descriptor = None
#       if constraint_descriptor is not None:
#         fetched_ref = fetch.scd.constraint_reference(utm_client, form.get_id())
#         op_req = reference_request_from_descriptor(constraint_descriptor)
#
#         # Query the DSS for other Constraints
#         fetch.scd.constraints()
#
#         # Query the DSS for other Constraints
#
#         # Create the
#
#         op_model.id = str(uuid.uuid4())
#         return flask.redirect(flask.url_for('constraint', id=op_model.id))
#     else:
#       for err in form.errors:
#         flask.flash('Could not validate provided information: {}'.format(err), 'error')
#   ops = models.Constraint.query
#   return flask.render_template('constraints.html', title='Constraints', form=form, ops=ops)


@webapp.route('/uss/v1/constraints/<id>', methods=['GET'])
@authorization.requires_scope([scd.SCOPE_SC, scd.SCOPE_CI])
def constraint_details(id: str):
  raw = db.get(db.TABLE_CONSTRAINTS, id)
  if raw is None:
    flask.abort(404, 'Could not find requested Constraint')
  owned_constraint = constraint.Owned(raw)
  return flask.jsonify({
    'constraint': owned_constraint.get_constraint_body(),
  })
