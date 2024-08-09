from flask import Blueprint, request, jsonify
import json
from database import query_db, execute_db
from flasgger import swag_from
from websocket_utils import broadcast

config_bp = Blueprint('config', __name__)

DEFAULT_CONFIG = {
    "autoRing": False,
    "autoRingMinSpan": 60,
    "autoRingMaxSpan": 600,
    "ringOnTime": 1,
    "ringOffTime": 1,
    "messages": True,
    "randomMessages": True,
    "ringCount": 4
}

def validate_config(data):
    errors = []

    if 'autoRing' in data and not isinstance(data['autoRing'], bool):
        errors.append("'autoRing' must be a boolean")
    if 'autoRingMinSpan' in data:
        if not isinstance(data['autoRingMinSpan'], int) or not (1 <= data['autoRingMinSpan'] <= 86400):
            errors.append("'autoRingMinSpan' must be an integer between 10 and 86400")
    if 'autoRingMaxSpan' in data:
        if not isinstance(data['autoRingMaxSpan'], int) or not (2 <= data['autoRingMaxSpan'] <= 86400):
            errors.append("'autoRingMaxSpan' must be an integer between 10 and 86400")
    if 'autoRingMinSpan' in data and 'autoRingMaxSpan' in data and data['autoRingMinSpan'] > data['autoRingMaxSpan']:
        errors.append("'autoRingMinSpan' must be less than or equal to 'autoRingMaxSpan'")
    if 'ringOnTime' in data:
        if not isinstance(data['ringOnTime'], int) or not (1 <= data['ringOnTime'] <= 30):
            errors.append("'ringOnTime' must be an integer between 1 and 30")
    if 'ringOffTime' in data:
        if not isinstance(data['ringOffTime'], int) or not (1 <= data['ringOffTime'] <= 30):
            errors.append("'ringOffTime' must be an integer between 1 and 30")
    if 'messages' in data and not isinstance(data['randomMessages'], bool):
        errors.append("'messages' must be a boolean")
    if 'randomMessages' in data and not isinstance(data['randomMessages'], bool):
        errors.append("'randomMessages' must be a boolean")
    if 'ringCount' in data:
        if not isinstance(data['ringCount'], int) or not (1 <= data['ringCount'] <= 10):
            errors.append("'ringCount' must be an integer between 1 and 10")

    return errors

@config_bp.route('/config', methods=['GET'])
@swag_from({
    'responses': {
        200: {
            'description': 'Configuration object',
            'schema': {
                'type': 'object',
                'properties': {
                    'autoRing': {'type': 'boolean'},
                    'autoRingMinSpan': {'type': 'integer'},
                    'autoRingMaxSpan': {'type': 'integer'},
                    'ringOnTime': {'type': 'integer'},
                    'ringOffTime': {'type': 'integer'},
                    'messages': {'type': 'boolean'},
                    'randomMessages': {'type': 'boolean'},
                    'ringCount': {'type': 'integer'}
                }
            }
        }
    },
    'tags': ['config']
})
def get_config():
    config = query_db('SELECT * FROM config WHERE id = 1', one=True)
    config_dict = dict(config)
    config_dict.pop('id', None)  # Remove the 'id' field from the dictionary
    return jsonify(config_dict), 200

@config_bp.route('/config', methods=['PUT', 'PATCH'])
@swag_from({
    'responses': {
        200: {
            'description': 'Updated configuration object',
            'schema': {
                'type': 'object',
                'properties': {
                    'autoRing': {'type': 'boolean'},
                    'autoRingMinSpan': {'type': 'integer'},
                    'autoRingMaxSpan': {'type': 'integer'},
                    'ringOnTime': {'type': 'integer'},
                    'ringOffTime': {'type': 'integer'},
                    'messages': {'type': 'boolean'},
                    'randomMessages': {'type': 'boolean'},
                    'ringCount': {'type': 'integer'}
                }
            }
        },
        400: {
            'description': 'Validation error',
            'schema': {
                'type': 'object',
                'properties': {
                    'errors': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        }
    },
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'schema': {
                'type': 'object',
                'properties': {
                    'autoRing': {'type': 'boolean'},
                    'autoRingMinSpan': {'type': 'integer'},
                    'autoRingMaxSpan': {'type': 'integer'},
                    'ringOnTime': {'type': 'integer'},
                    'ringOffTime': {'type': 'integer'},
                    'messages': {'type': 'boolean'},
                    'randomMessages': {'type': 'boolean'},
                    'ringCount': {'type': 'integer'}
                }
            }
        }
    ],
    'tags': ['config']
})
def update_config():
    data = request.get_json()
    errors = validate_config(data)
    
    if errors:
        return jsonify({'errors': errors}), 400

    current_config = query_db('SELECT * FROM config WHERE id = 1', one=True)
    current_config = dict(current_config)

    # Update the current config with new values
    updated_config = {**current_config, **data}

    execute_db('''
        UPDATE config
        SET autoRing = ?, autoRingMinSpan = ?, autoRingMaxSpan = ?, ringOnTime = ?, ringOffTime = ?, messages = ?, randomMessages = ?, ringCount = ?
        WHERE id = 1
    ''', (
        updated_config['autoRing'],
        updated_config['autoRingMinSpan'],
        updated_config['autoRingMaxSpan'],
        updated_config['ringOnTime'],
        updated_config['ringOffTime'],
        updated_config['messages'],
        updated_config['randomMessages'],
        updated_config['ringCount']
    ))

    # Once the config is updated, we need to send a new status via websocket
    # The message is "COMMAND:UPDATE_CONFIG", no additional data is needed
    # The message should be sent to all connected clients
    broadcast('COMMAND:UPDATE_CONFIG')

    updated_config.pop('id', None)  # Remove the 'id' field from the dictionary before returning
    return jsonify(updated_config), 200
