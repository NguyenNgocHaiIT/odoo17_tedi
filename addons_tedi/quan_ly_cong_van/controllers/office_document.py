import base64
import logging
from odoo import http
from odoo.http import request, Response
import json

_logger = logging.getLogger(__name__)

class AttachmentCreateAPI(http.Controller):

    @http.route('/api/quick/create/attachment', type='http', auth='public', methods=['POST'], csrf=False)
    def quick_create_attachment(self, **kwargs):
        print('hello')
        """
        API nhanh - chỉ cần file và res_id, tự động lấy tên từ file
        POST Parameters:
        - file: File upload (bắt buộc)
        - res_id: ID của công văn (bắt buộc)
        """
        try:
            file = kwargs.get('file')
            res_id = kwargs.get('res_id')
            model = 'project.project'

            if not file or not res_id:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Missing file or res_id'
                    }),
                    content_type='application/json',
                    status=400
                )

            # Get filename from file object
            if hasattr(file, 'filename'):
                name = file.filename
            else:
                name = f"attachment_{res_id}"

            # Validate res_id
            try:
                res_id = int(res_id)
            except ValueError:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'res_id must be an integer'
                    }),
                    content_type='application/json',
                    status=400
                )
            print(res_id)
            # Check record exists
            if not request.env[model].sudo().browse(res_id).exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': f'Record with ID {res_id} not found'
                    }),
                    content_type='application/json',
                    status=404
                )

            # Create attachment
            file_content = file.read()
            file_data = base64.b64encode(file_content)

            attachment = request.env['ir.attachment'].sudo().create({
                'name': name,
                'datas': file_data,
                'res_model': model,
                'res_id': res_id,
                'type': 'binary',
                'mimetype': file.content_type if hasattr(file, 'content_type') else 'application/octet-stream',
            })

            request.env.cr.commit()

            return Response(
                json.dumps({
                    'success': True,
                    'attachment_id': attachment.id,
                    'name': attachment.name
                }),
                content_type='application/json',
                status=201
            )

        except Exception as e:
            _logger.error(f"Quick create error: {str(e)}")
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json',
                status=500
            )