import os
import time
import random
import string
from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
import config

app = Flask(__name__, static_url_path='', static_folder=config.UPLOAD_FOLDER, template_folder=config.TEMPLATE_FOLDER)
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
data = {}
original_url_stats = {}  # New dictionary to track original URL stats

def clean():
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))

def generate_short_url(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

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
        while short_url in data:  # Ensure the short URL is unique
            short_url = generate_short_url()

        # Store the mapping
        data[short_url] = {
            'url': original_url,
            'vis': {},
            'count': 0
        }

        # Initialize original URL stats
        if original_url not in original_url_stats:
            original_url_stats[original_url] = {
                'count': 0,
                'vis': {}
            }

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
        return render_template('upload.html', warning=-1, link=request.base_url[:-6] + 'f=' + fid)

    if request.method == 'POST' and request.form.get('key').strip() == config.CLEAN_KEY:
        clean()

    return render_template('upload.html', warning=0)

@app.route('/f=<name>')
def showit(name: str):
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        if name in file:
            return render_template('showfile.html', image=not file.endswith('.pdf'), path=file)
    return render_template('showfile.html', path=-1)

@app.route('/q=<short_url>')
def redirect_page(short_url):
    if short_url not in data:
        return render_template('index.html', warning=5)

    original_url = data[short_url]['url']
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    # Track visits for the short URL
    if ip in data[short_url]['vis']:
        data[short_url]['vis'][ip] += 1
    else:
        data[short_url]['vis'][ip] = 1

    data[short_url]['count'] += 1  # Total click count

    # Update statistics for the original URL
    if ip in original_url_stats[original_url]['vis']:
        original_url_stats[original_url]['vis'][ip] += 1
    else:
        original_url_stats[original_url]['vis'][ip] = 1

    original_url_stats[original_url]['count'] += 1  # Total clicks for original URL

    return redirect(original_url)

@app.route('/stat', methods=['GET', 'POST'])
def get_count():
    if request.method == 'POST':
        original_url = request.form.get('URL').strip()

        if original_url in original_url_stats:
            return render_template('stats.html', data=original_url_stats, url=original_url, basic=False)
        else:
            return render_template('stats.html', basic=True, warning=True)

    return render_template('stats.html', basic=True)

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
