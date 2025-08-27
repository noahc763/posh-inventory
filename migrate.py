# migrate.py
from flask_migrate import Migrate
from models import db
from app import create_app   # uses your existing factory

app = create_app()
migrate = Migrate(app, db)

# Optional: flask shell convenience
@app.shell_context_processor
def make_shell_context():
    return {"db": db}
