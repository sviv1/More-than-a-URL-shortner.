import os
import time
import random
import string
from urllib.parse import urlparse
from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename  # we use it to save secure filenames it is utility provided by the Flask framework
                        # like ..//../lorem/ipsum/image.jpg -rm rf/ such files can produce vulnerabilities so we have to handle them
from flask_sqlalchemy import SQLAlchemy  # type: ignore    (Sqlite3 from SQLAlchemy)
from pytz import timezone 
from datetime import datetime
import config

IST = timezone('Asia/Kolkata')

# Initializing Flask and SQLAlchemy
app = Flask(__name__)
app.config.from_object(config)  # Import the config settings from config.py
db = SQLAlchemy(app)  # starting up the SQLAlchemy instance

#  allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

# a model for URL mappings more like a table but ORM feature or advantage as class work as tables and rows as the objects of class
class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500), nullable=False)
    short_url = db.Column(db.String(50), nullable=False, unique=True)
    visit_count = db.Column(db.Integer, default=0)  # visit count is the total visits to an orig url
   
    
    def __repr__(self):
        return f'<URL {self.short_url}>'

# a model for Visit information
class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False)  # IP address of the visitor
    url_mapping_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)  # ForeignKey to URL model
    timestamp = db.Column(db.DateTime, default=lambda:datetime.now(IST))  # Timestamp for visit
    url_mapping = db.relationship('URL', backref='visits', lazy=True) #lazy is telling how the loading of data is happenging onlhy when the request of it is made

    def __repr__(self):
        return f'<Visit {self.ip_address}>'

with app.app_context():
    db.create_all()  # Creates all the tables

#  application routes
@app.route('/')
def aux():
    return redirect(url_for('.forms'))


@app.route('/main', methods=['GET', 'POST'])
def forms():
    if request.method == 'POST':
        original_url = request.form.get("original_url").strip().strip('/')

        if original_url == "":
            return render_template('index.html', warning=1)
        
        if not is_valid_url(original_url):
            return render_template('index.html', warning=3)

           #  a new unique short URL for each submission
        short_url = generate_short_url()  # Generate a new short URL

        #  the short URL is unique in the database
        while URL.query.filter_by(short_url=short_url).first():
            short_url = generate_short_url()  # Regenerate if not unique

            # Create a new entry in the database with the original and short URL
        new_url = URL(original_url=original_url, short_url=short_url, visit_count=1)
        db.session.add(new_url)
        db.session.commit()  # Commit the changes

        
        full_short_url = request.base_url[:-4] + 'q=' + short_url # full valid url with base same
        return render_template('index.html', short_url=full_short_url)  # Return the shortened URL to the user

    return render_template('index.html')


@app.route('/q=<short_url>')
def redirect_page(short_url):
    # Query the URL model by short_url to get the original URL
    url_entry = URL.query.filter_by(short_url=short_url).first()

    if not url_entry:
        # If the short URL is not found, show a warning message
        return render_template('index.html', warning=5)

    original_url = url_entry.original_url  # Get the original URL from the URL model

    # Track each visit to the short URL
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)  # Get visitor's IP
    timestamp_ist = datetime.now(IST)  # Get the current time in IST
    new_visit = Visit(ip_address=ip, url_mapping_id=url_entry.id, timestamp=timestamp_ist)  # Use url_mapping_id to get the results because of the foreighn key mapping id
    
    db.session.add(new_visit)  # Add the visit record to the session
    db.session.commit()  # Commit the session to the database

    # Redirect the user to the original URL
    return redirect(original_url)

@app.route('/stat', methods=['GET', 'POST'])
def get_count():
    if request.method == 'POST':
        original_url = request.form.get('URL').strip()

        # Query the URL model to find all entries for the original URL
        url_entries = URL.query.filter_by(original_url=original_url).all()

        if url_entries:
            # Get all visit records for all short URLs associated with the original URL
            visits = []
            for url_entry in url_entries:
                # For each URL entry, fetch the visits based on its id (url_mapping_id)
                visit_records = Visit.query.filter(Visit.url_mapping_id == url_entry.id).all()

                # Add the short_url to each visit record
                for visit in visit_records:
                    visit.short_url = url_entry.short_url  # Add the short_url to the visit

                visits += visit_records  # Accumulate all visits for the original URL

            # Prepare statistics to send to the template
            stats = {
                'original_url': original_url,
                'short_urls': [url_entry.short_url for url_entry in url_entries],  # List all short URLs
                'total_visits': len(visits),  # Total visits is the number of records in the Visit table
                'visit_records': visits
            }

            return render_template('stats.html', stats=stats)

        else:
            # If no matching URL entries found, show a warning
            return render_template('stats.html', warning=True, basic=False)

    return render_template('stats.html', basic=True)




@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST' and request.form.get('key').strip() == config.MASTER_KEY:
        file = request.files['file']
        if not file or file.filename == '':
            return render_template('upload.html', warning=1)
        if file.filename.split('.')[-1] not in ALLOWED_EXTENSIONS:
            return render_template('upload.html', warning=2)

        filename = secure_filename(file.filename)
       # fid = ''.join(map(str, list(time.gmtime())[1:-3]))
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        link = url_for('uploaded_file', filename=filename)
        return render_template('upload.html', warning=-1, link=link)
        
    if request.method == 'POST' and request.form.get('key').strip() == config.CLEAN_KEY:
        clean()

    return render_template('upload.html', warning=0)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# @app.route('/f=<name>')
# def showit(name: str):
#     files = os.listdir(app.config['UPLOAD_FOLDER'])
#     for file in files:
#         if name in file:
#             return render_template('showfile.html', image=not file.endswith('.pdf'), path=file)
#     return render_template('showfile.html', path=-1)






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

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])  # Ensures both scheme (http/https) and netloc (domain) are present
    except ValueError:
        return False



def clean():
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))


if __name__ == '__main__':
    app.run(debug='true') # debug true only when developing so that easy to find out the mistakes of mine
