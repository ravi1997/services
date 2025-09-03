# Example Marshmallow schema for SMS
from marshmallow import Schema, fields

class SMSSchema(Schema):
	to = fields.String(required=True)
	message = fields.String(required=True)
