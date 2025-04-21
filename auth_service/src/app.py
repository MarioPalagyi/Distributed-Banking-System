from flask import Flask, request
from flask_restx import Api, Resource, fields
from authentication import authenticate, verify_token, AuthorizationError
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'authentication_logging.log',
            'maxBytes': 1000000,
            'backupCount': 3,
            'formatter': 'default',
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['file']
    }
})

app = Flask(__name__)

@app.before_request
def log_request_info():
    app.logger.debug("REQUEST --- Source: %s, Destination: %s, Headers: %s, Metadata: %s, Body: %s",
        request.remote_addr,
        request.url,
        dict(request.headers),
        dict(request.args) if request.args else None,
        request.get_data(as_text=True)
    )

@app.after_request
def log_response_info(response):
    if response.direct_passthrough:
        response.direct_passthrough = False

    content_type = response.headers.get("Content-Type", "")
    loggable_types = ["text/", "application/json", "application/xml"] # filter for these types of responses, to avoid large blobs of text

    if not any(content_type.startswith(t) for t in loggable_types):
        body = f"<{content_type} not logged>"
    else:
        try:
            body = response.get_data(as_text=True)
            # There are some large bodies of text during logging, we can make them shorter by uncommenting the following 2 lines:
            # if len(body) > 1000:
            #     body = body[:1000] + "... [shortened]"
        except Exception:
            body = "<body is unreadable>"
    app.logger.debug("RESPONSE --- Source: %s, Destination: %s, Headers: %s, Metadata: %s, Body: %s",
                     request.url,
                     request.remote_addr,
                     dict(response.headers),
                     None, body)
    return response

api = Api(app, 
          title='Authentication Service', 
          description='Authentication service for DS project',
          version='0.4.22')

# Namespace definition for organization
auth_ns = api.namespace('auth', description='Authentication services')

# Request and Response models; m = model, r = response
login_m = api.model('Login', 
                    {
                    'username': fields.String(required = True, description = 'User Username'),
                    'password': fields.String(required = True, description = 'User Password')
                    })

token_m = api.model('Token', 
                    {
                        'token': fields.String(required = True, description = 'Authentication Token'),
                        'role': fields.String(required = True, description = 'User Role')
                    })

verify_m = api.model('Verification', 
                     {
                        'username': fields.String(required=True, description = 'User Username'),
                        'token': fields.String(required = True, description = 'The Token to verify')
                     })

verify_r = api.model('VerifyResponse', 
                    {
                        'valid' : fields.Boolean(description = 'Token Validity ')
                    })

error_m = api.model('Error', 
                    {
                        'error': fields.String(description = 'Error Message')
                    })

@auth_ns.route('/login')
class Login(Resource):
    @api.expect(login_m)
    @api.response(200, 'Success', token_m)
    @api.response(401, 'Authentication Failed', error_m)
    def post(self):
        """Login with username and password -> token"""
        try:
            data = request.json
            if not data or 'username' not in data or 'password' not in data:
                return {'error': 'Missing username or password information'}, 400
            
            try:
                result = authenticate(data['username'], data['password'])
                return result, 200
            except AuthorizationError as e:
                return {'error': str(e)}, 401

        except Exception as e:
            return {'error': str(e)}, 500

@auth_ns.route('/authenticate')
class Verify(Resource):
    @api.expect(verify_m)
    @api.response(200, 'Success', verify_r)
    @api.response(400, 'Bad Request', error_m)
    def post(self):
        """Verify token validity"""
        try:
            data = request.json
            if not data or 'username' not in data or 'token' not in data:
                return {'error': 'Missing username or token'}, 400

            is_valid = verify_token(data['username'], data['token'])
            return {'validity': is_valid}, 200
        except Exception as e:
            return {'error': str(e)}, 500


if __name__ == '__main__':
    app.run(debug=True, port= 8000)