import os

# Define folder paths relative to the base directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'upload')  # Ensure this points to the correct location
TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')  # Ensure this points to the correct location

# Keys for file upload and clean operations
MASTER_KEY = 'admin123'
CLEAN_KEY = 'clean123'
SECRET_KEY = os.urandom(24) 

# Database URI for SQLAlchemy
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False  # Optional, to disable a warning
