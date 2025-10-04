from marshmallow import Schema, fields, validates, ValidationError, validate
import re

class SMSSchema(Schema):
	to = fields.String(required=True, validate=[validate.Length(min=6, max=16)])
	message = fields.String(required=True, validate=[validate.Length(min=1, max=500)])

	@validates('to')
	def validate_to(self, value, **kwargs):
		# Sanitize input
		v = str(value).strip()
		if not v:
			raise ValidationError('Phone number is required')
		# Accept either E.164 (+ and digits) or plain 6-15 digits; normalize optional '+'
		if not (re.fullmatch(r'\+[1-9]\d{5,14}', v) or re.fullmatch(r'[1-9]\d{5,14}', v)):
			raise ValidationError('Invalid phone number format')
		# Length check
		if len(v) < 6 or len(v) > 16:
			raise ValidationError('Phone number length must be 6-16 digits')

	@validates('message')
	def validate_message(self, value, **kwargs):
		# Sanitize input
		msg = str(value).strip()
		if not msg:
			raise ValidationError('Message is required')
		# Length check
		if len(msg) < 1 or len(msg) > 500:
			raise ValidationError('Message length must be 1-500 characters')
		# Prevent basic injection attacks (no script tags, no SQL keywords)
		if re.search(r'<script|SELECT|INSERT|UPDATE|DELETE|DROP|--', msg, re.IGNORECASE):
			raise ValidationError('Message contains forbidden content')
