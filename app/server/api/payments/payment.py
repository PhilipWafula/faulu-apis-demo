# third party imports
from flask import Blueprint
from flask import jsonify
from flask import make_response
from flask import request
from flask.views import MethodView
from jsonschema.exceptions import ValidationError

# application imports
from app import config
from app.server.models.mpesa_transaction import MpesaTransaction
from app.server.schemas.json import payment
from app.server.utils.enums.transaction_enums import MpesaTransactionType
from app.server.utils.payments.africas_talking import AfricasTalking
from app.server.utils.auth import requires_auth
from app.server.utils.validation import validate_request
from app.server.templates.responses import (
    invalid_payment_type,
    invalid_payments_service_provider,
    invalid_request_on_validation,
)

payments_blueprint = Blueprint("payments", __name__)


class PaymentAPI(MethodView):
    """
    Receives payment details.
    """

    def __init__(self):
        self.africas_talking_payments_client = AfricasTalking(
            config.AFRICASTALKING_API_KEY, config.AFRICASTALKING_USERNAME)

    @requires_auth(authenticated_roles=['ADMIN'])
    def get(self):
        payments_service_provider = request.args.get('payments_service_provider', None)
        if payments_service_provider and payments_service_provider == 'africas_talking':
            response, status_code = self.africas_talking_payments_client.get_wallet_balance_request()
            return make_response(jsonify(response), status_code)
        else:
            response = {
                'error': {
                    'message': 'Invalid payments service provide.',
                    'status': 'Fail'
                }
            }
            return make_response(jsonify(response), 403)

    @requires_auth(authenticated_roles=['ADMIN'])
    def post(self):
        payment_data = request.get_json()

        payments_service_provider = payment_data.get('payments_service_provider', None)
        payment_type = payment_data.get('payment_type', None)

        if payments_service_provider == 'africas_talking':
            if payment_type == 'business_to_business':
                # verify request
                try:
                    validate_request(
                        instance=payment_data,
                        schema=payment.africas_talking_business_to_business_json_schema)

                except ValidationError as error:
                    response, status_code = invalid_request_on_validation(error.message)
                    return make_response(jsonify(response), status_code)

                # make util call to create business to business transaction
                business_to_business_transaction = \
                    self.africas_talking_payments_client.create_business_to_business_transaction(
                        amount=payment_data.get('amount'),
                        destination_channel=payment_data.get('destination_channel'),
                        destination_account=payment_data.get('destination_account'),
                        product_name=payment_data.get('product_name'),
                        provider=payment_data.get('provider'),
                        transfer_type=payment_data.get('transfer_type'),
                        currency_code=payment_data.get('currency_code', "KES"),
                        metadata=payment_data.get('metadata')
                    )

                # initiate b2b transaction
                self.africas_talking_payments_client.initiate_business_to_business_transaction(
                    business_to_business_transaction=business_to_business_transaction
                )

                response = {
                    'message': 'Business to business transaction initiated successfully.',
                    'status': 'Success'
                }
                return make_response(jsonify(response), 200)

            elif payment_type == 'business_to_consumer':
                # verify request
                try:
                    validate_request(
                        instance=payment_data,
                        schema=payment.africas_talking_business_to_consumer_json_schema)

                except ValidationError as error:
                    response, status_code = invalid_request_on_validation(error.message)
                    return make_response(jsonify(response), status_code)

                business_to_consumer_transaction = \
                    self.africas_talking_payments_client.create_business_to_consumer_transaction(
                        amount=payment_data.get('amount'),
                        phone_number=payment_data.get('phone_number'),
                        product_name=payment_data.get('product_name'),
                        currency_code=payment_data.get('currency_code'),
                        metadata=payment_data.get('metadata'),
                        name=payment_data.get('name'),
                        provider_channel=payment_data.get('provider_channel'),
                        reason=payment_data.get('reason')
                    )

                # initiate b2c transaction
                self.africas_talking_payments_client.initiate_business_to_consumer_transaction(
                    business_to_consumer_transaction=business_to_consumer_transaction
                )

                response = {
                    'message': 'Business to consumer transaction initiated successfully.',
                    'status': 'Success'
                }
                return make_response(jsonify(response), 200)

            elif payment_type == 'mobile_checkout':
                # verify request
                try:
                    validate_request(
                        instance=payment_data,
                        schema=payment.africas_talking_checkout_json_schema)

                except ValidationError as error:
                    response, status_code = invalid_request_on_validation(error.message)
                    return make_response(jsonify(response), status_code)

                mobile_checkout_transaction = \
                    self.africas_talking_payments_client.create_mobile_checkout_transaction(
                        amount=payment_data.get('amount'),
                        phone_number=payment_data.get('phone_number'),
                        product_name=payment_data.get('product_name'),
                        currency_code=payment_data.get('currency_code'),
                        metadata=payment_data.get('metadata'),
                        provider_channel=payment_data.get('provider_channel')
                    )

                # initiate mobile checkout
                self.africas_talking_payments_client.initiate_mobile_checkout_transaction(
                    mobile_checkout_transaction=mobile_checkout_transaction
                )

                response = {
                    'message': 'Mobile checkout transaction initiated successfully.',
                    'status': 'Success'
                }
                return make_response(jsonify(response), 200)

            else:
                response, status_code = invalid_payment_type(payment_type)
                return make_response(jsonify(response), status_code)

        else:
            response, status_code = invalid_payments_service_provider(payments_service_provider)
            return make_response(jsonify(response), status_code)


class RetryPaymentAPI(MethodView):

    def __init__(self):
        self.africas_talking_payments_client = AfricasTalking(
            config.AFRICASTALKING_API_KEY, config.AFRICASTALKING_USERNAME)

    @requires_auth(authenticated_roles=['ADMIN'])
    def post(self):

        payment_retrial_data = request.get_json()

        # get service provider transaction id
        service_provider_transaction_id = payment_retrial_data.get('service_provider_transaction_id')

        # get mpesa transaction to retry
        response, status_code = self.africas_talking_payments_client.get_transaction_data(
            service_provider_transaction_id=service_provider_transaction_id
        )

        if status_code == 200:
            if response.get('status') == 'Success':

                # get mpesa transaction data
                mpesa_transaction_data = response.get('data')

                # get transaction type and idempotency key:
                local_mpesa_transaction = MpesaTransaction.query.filter_by(
                    service_provider_transaction_id=service_provider_transaction_id
                ).first()
                idempotency_key = local_mpesa_transaction.idempotency_key
                transaction_type = local_mpesa_transaction.type

                # get generic transaction data extract currency from value of format: "KES 2900.0000"
                value = mpesa_transaction_data.get('value').split()
                amount = float(value[1])
                currency_code = value[0]

                # retry transaction
                if mpesa_transaction_data.get('status') == 'Failed':
                    if transaction_type == MpesaTransactionType.MOBILE_CHECKOUT:

                        # build mobile checkout transaction to retry
                        mobile_checkout_transaction = \
                            self.africas_talking_payments_client.create_mobile_checkout_transaction(
                                amount=amount,
                                phone_number=mpesa_transaction_data.get('source'),
                                product_name=mpesa_transaction_data.get('productName'),
                                currency_code=currency_code,
                                metadata=mpesa_transaction_data.get('requestMetadata'),
                                provider_channel=mpesa_transaction_data.get('providerChannel')
                            )

                        # initiate retrial
                        self.africas_talking_payments_client.initiate_mobile_checkout_transaction(
                            idempotency_key=idempotency_key,
                            mobile_checkout_transaction=mobile_checkout_transaction
                        )

                        response = {
                            'message': 'Mobile checkout transaction retrial initiated successfully.',
                            'status': 'Success'
                        }
                        return make_response(jsonify(response), 200)

                    elif transaction_type == MpesaTransactionType.MOBILE_BUSINESS_TO_CONSUMER:
                        business_to_consumer_transaction = \
                            self.africas_talking_payments_client.create_business_to_consumer_transaction(
                                amount=amount,
                                phone_number=mpesa_transaction_data.get('destination'),
                                product_name=mpesa_transaction_data.get('productName'),
                                currency_code=currency_code,
                                metadata=mpesa_transaction_data.get('requestMetadata'),
                                provider_channel=mpesa_transaction_data.get('providerChannel')
                            )

                        # initiate b2c transaction
                        self.africas_talking_payments_client.initiate_business_to_consumer_transaction(
                            idempotency_key=idempotency_key,
                            business_to_consumer_transaction=business_to_consumer_transaction
                        )

                        response = {
                            'message': 'Business to consumer transaction retrial initiated successfully.',
                            'status': 'Success'
                        }
                        return make_response(jsonify(response), 200)

                    else:
                        response = {
                            'error': {
                                'message': f'Cannot retry transaction with status: {mpesa_transaction_data.get("status")}',
                                'status': 'Fail'
                            }
                        }
                    return make_response(jsonify(response), 403)
                else:
                    response = {
                        'error': {
                            'message': f'Unrecognized transaction type {transaction_type}',
                            'status': 'Fail'
                        }
                    }
                    return make_response(jsonify(response), 403)
            else:
                response = {
                    'error': {
                        'message': response.get("errorMessage"),
                        'status': "Fail"
                    }
                }
                return make_response(jsonify(response), 500)
        else:
            return make_response(jsonify(response), status_code)


create_payments_view = PaymentAPI.as_view("create_payments_view")
get_wallet_balance = PaymentAPI.as_view("wallet_balance_view")

retry_payments_view = RetryPaymentAPI.as_view("retry_payments_view")

payments_blueprint.add_url_rule(
    "/payments/",
    view_func=create_payments_view,
    methods=["POST"]
)

payments_blueprint.add_url_rule(
    "/payments/retry/",
    view_func=retry_payments_view,
    methods=["POST"]
)

payments_blueprint.add_url_rule(
    "/wallet_balance/",
    view_func=get_wallet_balance,
    methods=["GET"]
)