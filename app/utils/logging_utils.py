import json
from logging import Formatter

class JsonFormatter(Formatter):
    def format(self, record):
        payload = {
            'ts': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        extra = getattr(record, 'extra', None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)

def json_extra(**kwargs):
    return {'extra': kwargs}