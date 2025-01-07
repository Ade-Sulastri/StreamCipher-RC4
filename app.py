import os
import io

import numpy as np
from flask import Flask, redirect, render_template, request, url_for, send_from_directory, send_file
from PIL import Image

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def KSA(key):
    key_length = len(key)
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % key_length]) % 256
        S[i], S[j] = S[j], S[i]
    return S


def PRGA(S):
    i = 0
    j = 0
    while True:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        K = S[(S[i] + S[j]) % 256]
        yield K


def rc4_encrypt(key, plaintext):
    key = [ord(c) for c in key]
    S = KSA(key)
    keystream = PRGA(S)
    ciphertext = []
    for char in plaintext:
        encrypted_char = ord(char) ^ next(keystream)
        ciphertext.append(encrypted_char)
    return bytes(ciphertext)


def hide_message(image_path, message, key, output_path):
    # encrypt message
    encrypted_data = rc4_encrypt(key, message)

    # convert encrypted data to binary string
    binary_data = ''.join(format(byte, '08b') for byte in encrypted_data)

    message_length = format(len(binary_data), '032b')
    binary_data = message_length + binary_data

    # open and convert image
    img = Image.open(image_path)
    data = np.array(img, dtype=np.uint8)  # Explicitly set dtype to uint8

    # check if image can hold message
    if len(binary_data) > data.size:
        raise ValueError("Message is too large for this image")

    flat_data = data.flatten()

    for i, bit in enumerate(binary_data):
        # Clear the least significant bit and set it to the message bit
        flat_data[i] = (flat_data[i] & 254) | int(
            bit)  # 254 is 11111110 in binary

    modified_data = flat_data.reshape(data.shape)
    modified_img = Image.fromarray(modified_data)
    modified_img.save(output_path)


def extract_message(image_path, key):
    # load img
    img = Image.open(image_path)
    data = np.array(img)
    flat_data = data.flatten()

    length_bits = ''.join(str(pixel & 1) for pixel in flat_data[:32])
    message_length = int(length_bits, 2)

    # ekstrak pesan bits
    message_bits = ''.join(str(pixel & 1)
                           for pixel in flat_data[32:32+message_length])

    message_bytes = []
    for i in range(0, len(message_bits), 8):
        byte = int(message_bits[i:i+8], 2)
        message_bytes.append(byte)

    key_stream = PRGA(KSA([ord(c) for c in key]))
    decrypted = []
    for byte in message_bytes:
        decrypted_char = chr(byte ^ next(key_stream))
        decrypted.append(decrypted_char)

    return ''.join(decrypted)


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        input_img = request.files['file']
        input_message = request.form['message']
        input_key = request.form['key']

        if input_img and input_message and input_key:
            input_path = os.path.join(
                app.config['UPLOAD_FOLDER'], input_img.filename)
            input_img.save(input_path)

            output_path = os.path.join(
                app.config['UPLOAD_FOLDER'], 'output.png')
            try:
                hide_message(input_path, input_message, input_key, output_path)
                return render_template('index.html', output_image=output_path)
            except Exception as e:
                return render_template('index.html', error=str(e))
    return render_template('index.html')


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


def extract_only_message(image_path, key):
    try:
        extract_message = extract_message(image_path, key)

        with open('extracted_message.txt', 'w') as f:
            f.write(extract_message)

        print("Message extracted and saved to 'extracted_message.txt'")
        print(f"Mesaage content: {extract_message}")
    except Exception as e:
        print(f"Error: {e}")


@app.route('/ekstrak.html', methods=['GET', 'POST'])
def ekstrak():
    if request.method == 'POST':
        if 'file_extract' not in request.files:
            return render_template('ekstrak.html', error_extract="No file uploaded")
        
        input_img = request.files['file_extract']
        input_key = request.form.get('key_extract', '').strip()
        
        # Validasi input
        if not input_img or input_img.filename == '':
            return render_template('ekstrak.html', error_extract="No file selected")
        
        if not input_key:
            return render_template('ekstrak.html', error_extract="Key is required")
            
        try:
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_extract.png')
            input_img.save(input_path)
            extracted_message = extract_message(input_path, input_key)
            return render_template('ekstrak.html', extracted_message=extracted_message)
        except Exception as e:
            return render_template('ekstrak.html', error_extract=str(e))
    
    return render_template('ekstrak.html')

# Add new route for downloading the message
@app.route('/download_message')
def download_message():
    message = request.args.get('message', '')
    
    # Create in-memory text file
    message_bytes = io.BytesIO()
    message_bytes.write(message.encode())
    message_bytes.seek(0)
    
    return send_file(
        message_bytes,
        mimetype='text/plain',
        as_attachment=True,
        download_name='extracted_message.txt'
    )


if __name__ == '__main__':
    app.run(debug=True)