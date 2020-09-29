import flask
import flask_login
from werkzeug.exceptions import HTTPException

from monitoring.monitorlib import versioning
from monitoring.mockuss import webapp
from monitoring.mockuss.auth import authorization


@webapp.route('/')
@flask_login.login_required
def index():
  return flask.render_template('index.html', title='Home')


@webapp.route('/status')
def status():
  return 'Ok SimUSS {}'.format(versioning.get_code_version())


# @webapp.errorhandler(Exception)
# def handle_exception(e):
#   result = None #scd.handle_exception(e)
#   if result is not None:
#     return result
#
#   if isinstance(e, HTTPException):
#     return e
#   elif isinstance(e, authorization.InvalidScopeError):
#     return flask.jsonify({
#       'message': 'Invalid scope; expected one of {%s}, but received only {%s}' % (' '.join(e.permitted_scopes),
#                                                                                   ' '.join(e.provided_scopes))}), 403
#   elif isinstance(e, authorization.InvalidAccessTokenError):
#     return flask.jsonify({'message': e.message}), 401
#   elif isinstance(e, authorization.ConfigurationError):
#     return flask.jsonify({'message': e.message}), 500
#   elif isinstance(e, ValueError):
#     return flask.jsonify({'message': str(e)}), 400
#
#   return flask.jsonify({'message': str(e)}), 500


from .user import routes
from .constraints import routes
