from flask import Flask, request
from flask_restx import Api, Resource, fields
from sqlalchemy.orm import Session
from datetime import datetime
import random
import requests
from logging.config import dictConfig

from setupdb import Base, engine, Session
import dbmodels

# From Flask documentation: "If possible, configure logging before creating the application object."
dictConfig({
    'version': 1,
    'disable_existing_loggers': True,  # to disable console logging
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'transaction_logging.log',
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
          title="Transaction Service",
          description = "Transaction service for DS project",
          version="0.4.22",
          authorizations = {
              'apikey': {
                  'type': 'apiKey',
                  'in': 'header',
                  'name': 'Authorization'
              },
              'username': {
                  'type': 'apiKey',
                  'in': 'header',
                  'name': 'Username'
              }
          })

Base.metadata.create_all(bind=engine)

# Get DB session function
def get_db():
    db = Session()
    try:
        return db
    finally:
        db.close()

# Namespaces
transaction_ns = api.namespace('transactions', description='Transaction Services')
result_ns = api.namespace('results', description='Results ML Service')

transaction_m = api.model('Transaction', 
                    {
                    'customer': fields.String(required = True, description = 'Customer Identifier'),
                    'vendor_id': fields.String(required = True, description = 'Vendor Identifier'),
                    'amount': fields.Float(required = True, description = 'Transaction Amount')
                    })

transaction_r = api.model('TransactionResponse', 
                    {
                    'id': fields.Integer(description = 'Transaction ID'),
                    'customer': fields.String(description = 'Customer Identifier'),
                    'timestamp': fields.String(description = 'Transaction Timestamp'),
                    'status': fields.String(description = 'Transaction Status'),
                    'vendor_id': fields.String(description = 'Vendor Identifier'),
                    'amount': fields.String(description = 'Transaction Amount')
                    })

update_m = api.model('UpdateTransaction', {
    'status': fields.String(required=True, description = 'New Transaction Status')
})

result_r = api.model('ResultResponse',{
                     'id': fields.Integer(description = 'Result ID'), 
                     'transaction_id':fields.Integer(description = 'Transaction ID'),
                     'timestamp': fields.DateTime(description = 'Prediction Timestamp'),
                     'is_fraudulent': fields.Boolean(description = 'Fraud Prediction'),
                     'confidence': fields.Float(description = 'Prediction Confidence')
                    })

# Authentication middleware
def authenticate(request):
    token = request.headers.get('Authorization')
    if not token:
        return False, "No token identified", None
    
    username = request.headers.get('Username')
    if not username:
        return False, "No username provided", None
    
    if token.startswith("administrator") or token.startswith("agent"):
        role = token.split(':', 1)[0]
        return True, "", role
    else:
        return False, "Invalid token format or unauthorized role", None


# Randomised ML prediction System
def fraud_prediction_mock(transaction_id):
    return {
        'transaction_id': transaction_id,
        'is_fraudulent': random.choice([True, False]),
        'confidence': random.uniform(0.6, 0.99)
    }

@app.route('/')
def home():
    app.logger.info('Home page accessed')
    return 'Welcome to Flask Logging!'

@transaction_ns.route('/')
class TransactionList(Resource):
    @api.doc('list_transactions', security=[{'apikey': []}, {'username': []}])
    @api.response(200, 'Success', [transaction_r])
    @api.response(401, 'Unauthorized')
    def get(self):
        """List existing transactions"""
        authorised, message, role = authenticate(request)
        if not authorised:
            return {'error': message}, 401
        
        db = get_db()
        transactions = db.query(dbmodels.Transaction).all()
        transactions_list = []
        for t in transactions:
            transactions_list.append({
            'id': t.id,
            'customer':t.customer,
            'timestamp':t.timestamp.isoformat(), # normal datetime object is not JSON serializable, so we need ISO format
            'status':t.status.value, # .value gets str representation
            'vendor_id':t.vendor_id,
            'amount':t.amount
            })
        return transactions_list, 200
        
    @api.doc('make_transaction', security=[{'apikey': []}, {'username': []}])
    @api.expect(transaction_m)
    @api.response(201, 'Successfull transaction', transaction_r)
    @api.response(401, 'Unauthorized')
    def post(self):
        """Make a transaction"""
        authorized, message, role = authenticate(request)
        if not authorized:
            return {'error': message}, 401
        
        data = request.json
        db = get_db()

        new_transaction = dbmodels.Transaction(
            customer = data['customer'],
            vendor_id = data['vendor_id'],
            amount = data['amount'],
            status = dbmodels.TransactionStatus.submitted
        )

        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction) # Session.refresh refreshes column-oriented attributes with the current value available in the current transaction

        prediction = fraud_prediction_mock(new_transaction.id)

        new_result = dbmodels.Result(
            transaction_id = new_transaction.id,
            is_fraudulent = prediction['is_fraudulent'],
            confidence = prediction['confidence']
        )

        db.add(new_result)
        db.commit()

        return {
        'id':new_transaction.id,
        'customer':new_transaction.customer,
        'timestamp':new_transaction.timestamp.isoformat(), 
        'status':new_transaction.status.value, 
        'vendor_id':new_transaction.vendor_id,
        'amount':new_transaction.amount
        }, 201


@transaction_ns.route('/<int:id>')
@api.doc(params={'id':'Transaction ID'})
class TransactionsDetails(Resource):
    @api.doc('get_transaction', security=[{'apikey': []}, {'username': []}])
    @api.response(200, 'Success', transaction_r)
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    def get(self, id):
        """Query specific transaction"""
        authorized, message, role = authenticate(request)
        if not authorized:
            return {'error': message}, 401
        
        db = get_db()
        transaction = db.query(dbmodels.Transaction).filter_by(id=id).first() # Query WHERE id = id

        if not transaction:
            return {'error': 'Transaction not found'}, 404
        
        return {
            'id':transaction.id,
            'customer':transaction.customer,
            'timestamp':transaction.timestamp.isoformat(),
            'status':transaction.status.value,
            'vendor_id':transaction.vendor_id,
            'amount':transaction.amount
            }, 200
    
    @api.doc('update_transaction', security=[{'apikey': []}, {'username': []}])
    @api.expect(update_m)
    @api.response(200, 'Success', transaction_r)
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Transaction not found')
    def put(self, id):
        """Update status of transaction"""
        authorized, message, role = authenticate(request)
        if not authorized:
            return {'error': message}, 401
        
        data = request.json
        db = get_db()
        transaction = db.query(dbmodels.Transaction).filter_by(id=id).first()

        if not transaction:
            return {'error': 'Transaction not found by this ID'}, 404
        
        # Update Transaction Status
        try:
            new_status = dbmodels.TransactionStatus(data['status'])
            transaction.status = new_status
            db.commit()
            db.refresh(transaction)
        except ValueError:
            return {'error': 'Invalid Status code. Availabel codes: submitted, accepted, rejected'}, 400
        
        return {
            'id':transaction.id,
            'customer':transaction.customer,
            'timestamp':transaction.timestamp.isoformat(),
            'status':transaction.status.value,
            'vendor_id':transaction.vendor_id,
            'amount':transaction.amount
            }, 200
    

@result_ns.route('/')
class ResultList(Resource):
    @api.doc('list_results', security=[{'apikey': []}, {'username': []}])
    @api.response(200, 'Success', [result_r])
    @api.response(401, 'Unauthorized')
    def get(self):
        """Get all predictions"""
        authorized, message, role = authenticate(request)
        if not authorized:
            return {'error':message}, 401
        
        db = get_db()
        results = db.query(dbmodels.Result).all()
        results_list = []
        for r in results:
            results_list.append({
                'id':r.id,
                'transaction_id':r.transaction_id,
                'timestamp':r.timestamp.isoformat(),
                'is_fraudulent':r.is_fraudulent,
                'confidence':r.confidence
            })
        return results_list, 200


@result_ns.route('/transaction/<int:transaction_id>')
@api.doc(params={'transaction_id': 'The transaction ID'})
class ResultByTransaction(Resource):
    @api.doc('get_result_by_transaction', security=[{'apikey': []}, {'username': []}])
    @api.response(200, 'Success', [result_r])
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Result not found')
    def get(self, transaction_id):
        """Get the prediction result of one specific transaction"""
        authorized, message, role = authenticate(request)
        if not authorized:
            return {'error': message}, 401
        
        db = get_db()
        result = db.query(dbmodels.Result).filter_by(transaction_id=transaction_id).first()

        if not result:
            return {'error': 'No result found for corresponding transaction'}, 404
        
        return {
            'id':result.id,
            'transaction_id':result.transaction_id,
            'timestamp':result.timestamp.isoformat(),
            'is_fraudulent':result.is_fraudulent,
            'confidence':result.confidence,
        }, 200


if __name__ == '__main__':
    app.run(debug=True, port=8001) # port 8000 might be taken by authentication_service if run simultaneously