Quick fixes applied:
- Switched Flask-Login user_loader to use SQLAlchemy 2.x style: db.session.get(User, int(user_id)).
- Converted hard-coded nav links in base.html to url_for endpoints for reliability across environments.
No functional behavior was otherwise changed.
