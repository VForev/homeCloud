from flask import Flask, render_template, request, send_from_directory, redirect, url_for, send_file
import os
import uuid
import zipfile

app = Flask(__name__)
IMAGES_FOLDER = "images"
os.makedirs(IMAGES_FOLDER, exist_ok=True)
app.config['IMAGES_FOLDER'] = IMAGES_FOLDER

@app.route('/')
def images():
    image_files = os.listdir(IMAGES_FOLDER)
    return render_template('images.html', images=image_files, message=None)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'images' not in request.files:
        return redirect(url_for('images', message="No image part"))
    files = request.files.getlist('images')
    if not files:
        return redirect(url_for('images', message="No selected images"))
    
    uploaded_files = []
    for image in files:
        if image.filename == '':
            continue
        filename = str(uuid.uuid4()) + os.path.splitext(image.filename)[1]  # Unique filename
        image.save(os.path.join(app.config['IMAGES_FOLDER'], filename))
        uploaded_files.append(filename)
    
    return redirect(url_for('images', message="Images uploaded successfully" if uploaded_files else "No valid images uploaded"))

@app.route('/images/<filename>')
def get_image(filename):
    return send_from_directory(app.config['IMAGES_FOLDER'], filename)

@app.route('/download_images', methods=['POST'])
def download_images():
    selected_images = request.form.getlist('selected_images')
    if not selected_images:
        return redirect(url_for('images', message="No images selected for download"))
    
    zip_path = os.path.join(IMAGES_FOLDER, "downloaded_images.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for image in selected_images:
            zipf.write(os.path.join(IMAGES_FOLDER, image), image)
    
    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='192.168.1.83', port=8080, debug=True)

# Create the necessary HTML file for UI
images_html = """<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>Image Gallery</title>
    <script>
        function showMessage(message) {
            if (message) {
                const msgDiv = document.getElementById('message');
                msgDiv.innerText = message;
                msgDiv.style.display = 'block';
                setTimeout(() => { msgDiv.style.display = 'none'; }, 3000);
            }
        }
    </script>
</head>
<body onload="showMessage('{{ message }}')">
    <h1>Image Gallery</h1>
    <div id="message" style="display: none; position: fixed; top: 10px; right: 10px; background: lightgreen; padding: 10px; border-radius: 5px;">{{ message }}</div>
    <form action='/upload_image' method='post' enctype='multipart/form-data'>
        <input type='file' name='images' multiple>
        <button type='submit'>Upload Images</button>
    </form>
    <h2>Uploaded Images:</h2>
    <form action='/download_images' method='post'>
        {% for image in images %}
            <div>
                <input type='checkbox' name='selected_images' value='{{ image }}'>
                <img src='/images/{{ image }}' alt='{{ image }}' width='200'>
            </div>
        {% endfor %}
        <button type='submit'>Download Selected Images</button>
    </form>
</body>
</html>"""

# Save the HTML file
os.makedirs("templates", exist_ok=True)
with open("templates/images.html", "w") as f:
    f.write(images_html)
