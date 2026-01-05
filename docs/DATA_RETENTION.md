# Data Retention Policy

## Overview
This policy defines the retention period for sensitive data (PHI/PII) stored by the application to ensure compliance with privacy regulations (GDPR, HIPAA, DPDP) and minimize security risks.

## Policy Details
- **Retention Period:** 30 days (Default).
- **Data Types:** SMS Logs (`sms_messages`), Email Logs (`email_messages`).
- **Action:** Hard Delete (Permanent removal).

## Configuration
The retention period is configurable via Environment Variables:

```bash
# Data retention period in days
DATA_RETENTION_DAYS=30
```

## Automated Cleanup
A Celery task `cleanup_old_data` is implemented in `app/tasks/cleanup.py`.

### Running Manually
To trigger cleanup manually via Flask shell:
```python
from app.tasks.cleanup import cleanup_old_data
cleanup_old_data.delay()
```

### Scheduling
Ideally configure Celery Beat to run this task daily at midnight.
```python
# In celery_worker.py or config
CELERY_BEAT_SCHEDULE = {
    'cleanup-every-night': {
        'task': 'cleanup_old_data',
        'schedule': crontab(hour=0, minute=0),
    },
}
```
