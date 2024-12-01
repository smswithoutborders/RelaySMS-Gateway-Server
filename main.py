"""
Initializes a Flask app and registers API blueprints.
"""

from flask import Flask
from src.api_v2 import v2_blueprint
from src.api_v3 import v3_blueprint

app = Flask(__name__)

app.register_blueprint(v2_blueprint)
app.register_blueprint(v3_blueprint)
