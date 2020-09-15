import flask
import flask_login
from werkzeug.urls import url_parse

from monitoring.simuss import webapp
from . import forms, models


@webapp.route('/login', methods=['GET', 'POST'])
def login():
  if flask_login.current_user.is_authenticated:
    return flask.redirect(flask.url_for('index'))
  form = forms.LoginForm()
  if form.validate_on_submit():
    user = models.User(username=form.username.data)
    if user is None or not user.check_password(form.password.data):
      flask.flash('Invalid username or password')
      return flask.redirect(flask.url_for('login'))
    flask_login.login_user(user, remember=form.remember_me.data)
    next_page = flask.request.args.get('next')
    if not next_page or url_parse(next_page).netloc != '':
      next_page = flask.url_for('index')
    return flask.redirect(next_page)
  return flask.render_template('login.html', title='Log in', form=form)


@webapp.route('/logout')
def logout():
  flask_login.logout_user()
  return flask.redirect(flask.url_for('index'))
