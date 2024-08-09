from flask import Blueprint, request, jsonify
import os
import uuid
import time
from werkzeug.utils import secure_filename
from audio_utils import allowed_file, get_audio_length, validate_audio
from database import query_db, execute_db
from flasgger import swag_from
import zipfile
import io

messages_bp = Blueprint('messages', __name__)

UPLOAD_FOLDER = 'messages'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@messages_bp.route('/messages', methods=['POST'])
@swag_from({
    'summary': 'Upload a .wav file and create a record',
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'The .wav audio file to upload'
        }
    ],
    'responses': {
        201: {
            'description': 'Record created successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string'},
                    'recordTimestamp': {'type': 'integer'},
                    'length': {'type': 'integer'}
                }
            }
        },
        400: {
            'description': 'Invalid input or file type not allowed',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    },
    'tags': ['messages']
})
def create_record():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.wav")
        file.save(file_path)

        if not validate_audio(file_path):
            os.remove(file_path)
            return jsonify({'error': 'Audio file does not meet requirements (32-bit, 96KHz)'}), 400

        try:
            length = get_audio_length(file_path)
        except Exception as e:
            os.remove(file_path)
            return jsonify({'error': 'Invalid audio file'}), 400

        record_timestamp = int(time.time())

        execute_db('''
            INSERT INTO messages (id, recordTimestamp, length)
            VALUES (?, ?, ?)
        ''', (file_id, record_timestamp, length))

        return jsonify({'id': file_id, 'recordTimestamp': record_timestamp, 'length': length}), 201
    else:
        return jsonify({'error': 'File type not allowed'}), 400


@messages_bp.route('/messages', methods=['GET'])
@swag_from({
    'summary': 'Retrieve all messages',
    'responses': {
        200: {
            'description': 'A list of messages',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'recordTimestamp': {'type': 'integer'},
                        'length': {'type': 'integer'}
                    }
                }
            }
        }
    },
    'tags': ['messages']
})
def get_messages():
    messages = query_db('SELECT * FROM messages')
    return jsonify([dict(record) for record in messages]), 200

@messages_bp.route('/messages/<record_id>', methods=['DELETE'])
@swag_from({
    'summary': 'Delete a record by ID',
    'parameters': [
        {
            'name': 'record_id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'The ID of the record to delete'
        }
    ],
    'responses': {
        204: {
            'description': 'Record deleted successfully'
        },
        404: {
            'description': 'Record not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    },
    'tags': ['messages']
})
def delete_record(record_id):
    record = query_db('SELECT * FROM messages WHERE id = ?', [record_id], one=True)
    if record:
        file_path = os.path.join(UPLOAD_FOLDER, f"{record_id}.wav")
        if os.path.exists(file_path):
            os.remove(file_path)
        execute_db('DELETE FROM messages WHERE id = ?', [record_id])
        return '', 204
    else:
        return jsonify({'error': 'Record not found'}), 404

@messages_bp.route('/messages/<record_id>', methods=['GET'])
@swag_from({
    'summary': 'Retrieve a record by ID',
    'parameters': [
        {
            'name': 'record_id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'The ID of the record to retrieve'
        }
    ],
    'responses': {
        200: {
            'description': 'Record retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string'},
                    'recordTimestamp': {'type': 'integer'},
                    'length': {'type': 'integer'}
                }
            }
        },
        404: {
            'description': 'Record not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    },
    'tags': ['messages']
})
def get_record(record_id):
    record = query_db('SELECT * FROM messages WHERE id = ?', [record_id], one=True)
    if record:
        return jsonify(dict(record)), 200
    else:
        return jsonify({'error': 'Record not found'}), 404

@messages_bp.route('/messages/<record_id>/binary', methods=['GET'])
@swag_from({
    'summary': 'Retrieve the binary data of a record by ID',
    'parameters': [
        {
            'name': 'record_id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'The ID of the record to retrieve'
        }
    ],
    'responses': {
        200: {
            'description': 'Record binary data retrieved successfully',
            'schema': {
                'type': 'file'
            }
        },
        404: {
            'description': 'Record not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    },
    'tags': ['messages']
})
def get_record_binary(record_id):
    record = query_db('SELECT * FROM messages WHERE id = ?', [record_id], one=True)
    if record:
        file_path = os.path.join(UPLOAD_FOLDER, f"{record_id}.wav")
        return open(file_path, 'rb').read(), 200, {'Content-Type': 'audio/wav'}
    else:
        return jsonify({'error': 'Record not found'}), 404

# Gets all binaries that exist and returns them as a zip file
@messages_bp.route('/messages/allBinaries', methods=['GET'])
@swag_from({
    'summary': 'Retrieve all binary data of records as a zip file',
    'responses': {
        200: {
            'description': 'All binary data retrieved successfully',
            'schema': {
                'type': 'file'
            }
        }
    },
    'tags': ['messages']
})
def get_all_binaries():
    all_records = query_db('SELECT * FROM messages')
    with io.BytesIO() as zip_buffer:
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for record in all_records:
                record_id = record['id']
                record_timestamp = record['recordTimestamp']
                file_path = os.path.join(UPLOAD_FOLDER, f"{record_id}.wav")
                zip_file.write(file_path, f"{record_id}_{record_timestamp}.wav")
        zip_buffer.seek(0)
        return zip_buffer.read(), 200, {'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename=all_binaries.zip'}