import os
import time
import random
import string
from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from pytz import timezone
from datetime import datetime
import config

IST = timezone('Asia/Kolkata')

# Initialize Flask and SQLAlchemy
app = Flask(__name__)
app.config.from_object(config)  # Import the config settings from config.py
db = SQLAlchemy(app)  # Initialize the SQLAlchemy instance

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

# Define a model for URL mappings
class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500), nullable=False)
    short_url = db.Column(db.String(50), nullable=False, unique=True)
    visit_count = db.Column(db.Integer, default=0)  # Tracks total visits for short URL
    visitors = db.relationship('Visit', backref='url', lazy=True)  # Relationship to Visit model
    
    def __repr__(self):
        return f'<URL {self.short_url}>'

# Define a model for Visit information
class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False)  # IP address of the visitor
    url_mapping_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)  # ForeignKey to URL model
    count = db.Column(db.Integer, default=0)  # Count of visits from the same IP
    timestamp = db.Column(db.DateTime, default=lambda:datetime.now(IST))  # Timestamp for visit

    def __repr__(self):
        return f'<Visit {self.ip_address}>'

with app.app_context():
    db.create_all()  # Creates all the tables

# Define application routes
@app.route('/')
def aux():
    return redirect(url_for('.forms'))


@app.route('/main', methods=['GET', 'POST'])
def forms():
    if request.method == 'POST':
        original_url = request.form.get("original_url").strip().strip('/')
        if original_url == "":
            return render_template('index.html', warning=1)

        short_url = generate_short_url()
        
        # Ensure the short URL is unique in the database
        while URL.query.filter_by(short_url=short_url).first():
            short_url = generate_short_url()

        # Store the mapping in the database
        new_url_mapping = URL(original_url=original_url, short_url=short_url)
        db.session.add(new_url_mapping)
        db.session.commit()

        return render_template('index.html', a=request.base_url[:-4] + 'q=' + short_url, saved=True)

    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST' and request.form.get('key').strip() == config.MASTER_KEY:
        file = request.files['file']
        if not file or file.filename == '':
            return render_template('upload.html', warning=1)
        if file.filename.split('.')[-1] not in ALLOWED_EXTENSIONS:
            return render_template('upload.html', warning=2)

        filename = secure_filename(file.filename)
        fid = ''.join(map(str, list(time.gmtime())[1:-3]))
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        link = url_for('uploaded_file', filename=filename)
        return render_template('upload.html', warning=-1, link=link)

    if request.method == 'POST' and request.form.get('key').strip() == config.CLEAN_KEY:
        clean()

    return render_template('upload.html', warning=0)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/f=<name>')
def showit(name: str):
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        if name in file:
            return render_template('showfile.html', image=not file.endswith('.pdf'), path=file)
    return render_template('showfile.html', path=-1)


@app.route('/q=<short_url>')
def redirect_page(short_url):
    url_entry = URL.query.filter_by(short_url=short_url).first()  # Query the URL model by short_url

    if not url_entry:
        return render_template('index.html', warning=5)

    original_url = url_entry.original_url  # Get the original URL from the URL model
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    # Track visits for the short URL
    visit_entry = Visit.query.filter_by(url_mapping_id=url_entry.id, ip_address=ip).first()

    if visit_entry:
        visit_entry.count += 1  # Increment the visit count for this IP
    else:
        # If no record exists, create a new Visit entry
        new_visit = Visit(ip_address=ip, url_mapping_id=url_entry.id,count=1)
        db.session.add(new_visit)
    
    original_url_entries = URL.query.filter_by(original_url=original_url).all()
    for entry in original_url_entries:
        entry.visit_count += 1

    # Commit the changes to the database
    db.session.commit()


    return redirect(original_url)


@app.route('/stat', methods=['GET', 'POST'])
def get_count():
    if request.method == 'POST':
        original_url = request.form.get('URL').strip()

        # Query the URL model to find the original URL
        url_entry = URL.query.filter_by(original_url=original_url).first()

        if url_entry:
            # Fetch visits related to this URL
            visits = Visit.query.filter_by(url_mapping_id=url_entry.id).all()
            for visit in visits:
                visit.timestamp = visit.timestamp.astimezone(IST)
            # Prepare statistics to send to the template
            stats = {
                'original_url': original_url,
                'short_url': url_entry.short_url,
                'total_visits': url_entry.visit_count,
                'visit_records': visits
            }
            return render_template('stats.html', stats=stats)

        else:
            # If the URL isn't found in the database, show a warning
            return render_template('stats.html', warning=True, basic=False)

    return render_template('stats.html', basic=True)


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/reset', methods=['POST'])
def hard_reset():
    if request.form.get('key') == config.MASTER_KEY:  # Use your admin/master key for security
        # Clear the data from both tables
        try:
            db.session.query(URL).delete()  # Delete all records in the URL table
            db.session.query(Visit).delete()  # Delete all records in the Visit table
            db.session.commit()  # Commit the changes to the database
            
            flash('Database has been reset successfully!', 'success')  # Success message
        except Exception as e:
            db.session.rollback()  # Rollback in case of an error
            flash(f'Error occurred while resetting the database: {str(e)}', 'danger')  # Error message
        return redirect(url_for('aux'))  # Redirect to home page after reset
    else:
        flash('Unauthorized access. Invalid admin key.', 'danger')  # Invalid key message
        return redirect(url_for('stats'))  # Redirect back to stats page



@app.route('/clear_uploads', methods=['POST'])
def clear_uploads():
    admin_key = request.form.get('admin_key')
    if admin_key == config.CLEAN_KEY:  # Replace with your actual admin key
        clean()  # Call the function to clear the files
        return render_template('upload.html', warning=3)  # You can adjust the warning or success message here
    else:
        return render_template('upload.html', warning=4)  # Invalid admin key


# Helper functions
def generate_short_url(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def clean():
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))


if __name__ == '__main__':
    app.run(debug=True)
