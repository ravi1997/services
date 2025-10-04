from flask import Blueprint, current_app
import os
from datetime import datetime, timedelta
from app.utils.response import success, error
from app.utils.decorators import require_admin_bearer_and_log

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/logs/cleanup', methods=['POST'])
@require_admin_bearer_and_log
def log_cleanup():
    months = int(current_app.config.get('LOG_RETENTION_MONTHS', 8))
    cutoff = datetime.utcnow() - timedelta(days=30*months)
    log_dir = os.path.join(current_app.root_path, '..', 'logs')
    removed = []
    if os.path.isdir(log_dir):
        for f in os.listdir(log_dir):
            fp = os.path.join(log_dir, f)
            try:
                if os.path.isfile(fp) and datetime.utcfromtimestamp(os.path.getmtime(fp)) < cutoff:
                    os.remove(fp)
                    removed.append(f)
            except Exception:
                pass
    return success('Log cleanup complete', {'removed': removed})
