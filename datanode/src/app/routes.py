from app import webapp


@webapp.route('/status')
def status():
  return 'Ok'

from .scd import scd
