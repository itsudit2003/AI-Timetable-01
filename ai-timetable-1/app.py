from flask import Flask
from config import SECRET_KEY, FIXED_SLOTS
from models import init_db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.teacher import teacher_bp
from routes.export import export_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(teacher_bp)
app.register_blueprint(export_bp)

if __name__=='__main__':
    init_db()
    app.run(debug=True,host='0.0.0.0',port=5000)
