from marshmallow import Schema, fields, validates, ValidationError, validate
import phonenumbers

class SMSSchema(Schema):
	to = fields.String(required=True)
	message = fields.String(required=True, validate=validate.Length(min=1, max=500))

	@validates('to')
	def validate_to(self, value, **kwargs):
		if not isinstance(value, str) or not value.strip():
			raise ValidationError('Phone number is required')
		v = value.strip()
		if not v.startswith('+'):
			raise ValidationError('Phone number must be in E.164 format (start with +)')
		try:
			parsed = phonenumbers.parse(v, None)
			if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
				raise ValidationError('Invalid phone number')
		except Exception:
			raise ValidationError('Invalid phone number')
