from flask import Flask, request, render_template, redirect, session, url_for
import pymysql
import boto3
import os
import bcrypt
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_default_secret_key')  # Load from environment variable

# MySQL configuration - use environment variables or default values
db_host = 'test'
db_user = 'root'
db_password = 'Admin-123'
db_name = 'ccituserdb'
s3_Key = 'test'
s3_SecKey = 'test'
s3_bucket = 'ccitaugbatch'
s3_region = 'ap-south-1'

# Initialize AWS S3 client
s3 = boto3.client('s3', aws_access_key_id=s3_Key, aws_secret_access_key=s3_SecKey, region_name=s3_region)

# Initialize MySQL connection
db = pymysql.connect(host=db_host, user=db_user, password=db_password, database=db_name)

# Folder to store uploads (inside static folder for easy access)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads/')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file extensions for image upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Function to validate file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    # Clear session if needed
    session.pop('username', None)
    session.pop('email', None)
    session.pop('image_url', None)
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')  # Encode to bytes
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        image = request.files['image']

        # Check if the image is allowed and has a filename
        """ if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Ensure the uploads directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

            image.save(file_path)  # Save the file locally

            # Store the local file path (relative to the static folder) in the database
            relative_path = "uploads/{}".format(filename)  # Path relative to static folder
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, image_url) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, relative_path)
            )
            db.commit()
            cursor.close()
        """
            
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Upload image to S3
            s3.upload_file(
                os.path.join(app.config['UPLOAD_FOLDER'], filename),
                s3_bucket,
                filename,
                ExtraArgs={'ACL': 'public-read'}
            )

            # Get the image URL from S3
            image_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{filename}"

            # Insert user data into RDS MySQL
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, image_url) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, image_url)
            )
            db.commit()
            cursor.close()

            # Clean up the uploaded image file
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            return redirect('/signin')

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')  # Encode the password
        cursor = db.cursor()
        cursor.execute("SELECT password, name, email, image_url FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()

        # Verify the password using bcrypt
        if result and bcrypt.checkpw(password, result[0].encode('utf-8')):
            session['username'] = result[1]
            session['email'] = result[2]
            session['image_url'] = result[3]  # Local file path

            return redirect('/welcome')
        else:
            return "Invalid Credentials!"

    return render_template('signin.html')

@app.route('/welcome')
def welcome():
    # Check if the user is logged in
    if 'username' not in session:
        return redirect(url_for('signin'))

    # Ensure the image URL is accessible
    image_url = url_for('static', filename=session['image_url'])  # Serve the image from the static folder
    return render_template('welcome.html', username=session['username'], email=session['email'], image_url=image_url)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('email', None)
    session.pop('image_url', None)
    return redirect('/')

if __name__ == '__main__':
    # Ensure uploads directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(host='0.0.0.0', port=5000)  # Change to port 80 for HTTP access
