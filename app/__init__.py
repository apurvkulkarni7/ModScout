from flask import Flask
from app.config import AppConfig
from app.routes import routes_bp
import threading
from app.utils import background_scheduler

def create_app():
    app = Flask(__name__,instance_relative_config=True,template_folder='templates', static_folder='static')
    
    app_config = AppConfig()
    app.config.from_object(app_config)
    app.config['CUSTOM_CONFIG'] = app_config
    
    # Register Blueprints
    app.register_blueprint(routes_bp)

    # Schedule the auto update in background
    if app_config.auto_update_database == True:
        scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
        scheduler_thread.start()
    return app