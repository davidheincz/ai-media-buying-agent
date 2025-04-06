from flask import Flask, render_template_string
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Media Buying Agent</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { color: #333; }
            .container { max-width: 800px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AI Media Buying Agent</h1>
            <p>Your AI-driven media buying agent is running successfully!</p>
            <p>DeepSeek API Key: {{ deepseek_key }}</p>
        </div>
    </body>
    </html>
    """, deepseek_key=os.environ.get('DEEPSEEK_API_KEY', 'Not set'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
