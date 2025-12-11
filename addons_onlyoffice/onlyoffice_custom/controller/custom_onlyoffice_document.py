from os import write
import re
import json
import logging
import markupsafe
from odoo import _, http
from odoo.tests import users
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.onlyoffice_odoo.controllers.controllers import Onlyoffice_Connector
from odoo.addons.onlyoffice_odoo.utils import config_utils, file_utils, jwt_utils, url_utils
from odoo.addons.onlyoffice_odoo.controllers.controllers import onlyoffice_urlopen
import base64
from mimetypes import guess_type
import os
_logger = logging.getLogger(__name__)

_mobile_regex = r"android|avantgo|playbook|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od|ad)|iris|kindle|lge |maemo|midp|mmp|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\\/|plucker|pocket|psp|symbian|treo|up\\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino"  # noqa: E501


class OnlyofficeDocuments_custom(Onlyoffice_Connector):
    @http.route("/onlyoffice/share/<int:attachment_id>", auth="public", type="http", website=True)
    def render_share_editor(self, attachment_id, access_token=None):
        _logger.info("GET /onlyoffice/editor/%s", attachment_id)
        attachment = self.get_attachment(attachment_id)
        if not attachment:
            _logger.warning("GET /onlyoffice/editor/%s - attachment not found", attachment_id)
            return request.not_found()

        attachment.validate_access(access_token)

        data = attachment.sudo().read(["id", "checksum", "public", "name", "access_token"])[0]
        filename = data["name"]

        can_read = attachment.sudo().check_access_rights("read", raise_exception=False) and file_utils.can_view(
            filename)
        can_write = attachment.sudo().check_access_rights("write", raise_exception=False) and file_utils.can_edit(
            filename)

        if not can_read:
            _logger.warning("GET /onlyoffice/editor/%s - no read access", attachment_id)
            raise Exception("cant read")

        _logger.info("GET /onlyoffice/editor/%s - success", attachment_id)
        return request.render(
            "onlyoffice_odoo.onlyoffice_editor", self.prepare_share_editor_values(attachment, access_token, can_write)
        )

    def prepare_share_editor_values(self, attachment, access_token, can_write):
        _logger.info("prepare_editor_values - attachment: %s", attachment.id)
        document_share = http.request.env['document.share'].sudo().search([("document_id", "=", attachment.id)],
                                                                          limit=1)
        rolls = []
        roll_access = {
            "edit": True,
            "comment": True,
            "review": True,
            "copy": True,
            "print": True,
            "chat": True,
            "download": True,
            "rename": True,
        }
        current_user = request.env.user
        user_share = ''
        if not attachment.public:
            if document_share:
                public = document_share.public_access
                for rec in document_share.user_role_permision_ids:
                    if rec.user_id.id == current_user.id:
                        rolls = [rec.role_access for rec in rec.role_access_ids]
                        user_share = rec.user_id
                        roll_access = {
                            "edit": "edit" in rolls,
                            "comment": "comment" in rolls,
                            "review": "review" in rolls,
                            "copy": "copy" in rolls,
                            "print": "print" in rolls,
                            "chat": "chat" in rolls,
                            "download": "download" in rolls,
                            "rename": "rename" in rolls,
                        }
                        break
                if not public:
                    if request.env.user != attachment.sudo().create_uid and not user_share:
                        raise AccessError(_("User has no read access rights to open this document"))
                elif public and request.env.user != attachment.sudo().create_uid:
                    rolls_public = [roll_public.role_access for roll_public in document_share.role_access_ids]
                    roll_access = {
                        "edit": "edit" in rolls_public,
                        "comment": "comment" in rolls_public,
                        "review": "review" in rolls_public,
                        "copy": "copy" in rolls_public,
                        "print": "print" in rolls_public,
                        "chat": "chat" in rolls_public,
                        "download": "download" in rolls_public,
                        "rename": "rename" in rolls_public,
                    }
            elif request.env.user != attachment.sudo().create_uid:
                raise AccessError(_("User has no read access rights to open this document"))

        if attachment.public and request.env.user != attachment.sudo().create_uid:
            roll_access = {
                "edit": False,
                "comment": False,
                "review": False,
                "copy": False,
                "print": False,
                "chat": False,
                "download": False,
                "rename": False,
            }

        data = attachment.sudo().read(["id", "checksum", "public", "name", "access_token"])[0]
        key = str(data["id"]) + str(data["checksum"])
        docserver_url = config_utils.get_doc_server_public_url(request.env)
        odoo_url = config_utils.get_base_or_odoo_url(request.env)

        filename = self.filter_xss(data["name"])

        security_token = jwt_utils.encode_payload(
            request.env, {"id": request.env.user.id}, config_utils.get_internal_jwt_secret(request.env)
        )
        security_token = security_token.decode("utf-8") if isinstance(security_token, bytes) else security_token
        access_token = access_token.decode("utf-8") if isinstance(access_token, bytes) else access_token
        path_part = (
                str(data["id"])
                + "?oo_security_token="
                + security_token
                + ("&access_token=" + access_token if access_token else "")
                + "&shardkey="
                + key
        )

        document_type = file_utils.get_file_type(filename)

        is_mobile = bool(re.search(_mobile_regex, request.httprequest.headers.get("User-Agent"), re.IGNORECASE))

        root_config = {
            "width": "100%",
            "height": "100%",
            "type": "mobile" if is_mobile else "desktop",
            "documentType": document_type,
            "document": {
                "title": filename,
                "url": odoo_url + "onlyoffice/file/content/" + path_part,
                "fileType": file_utils.get_file_ext(filename),
                "key": key,
                "permissions": {"edit": False},
            },
            "editorConfig": {
                "mode": "view",
                "lang": request.env.user.lang,
                "user": {"id": str(request.env.user.id), "name": request.env.user.name},
                "customization": {
                    'autosave': True,
                    'forcesave': True,
                },

                'coEditing': {
                    'mode': "fast",
                    'change': False
                }
            },
        }

        if can_write:
            root_config["editorConfig"]["callbackUrl"] = odoo_url + "onlyoffice/editor/callback/" + path_part

        if not roll_access.get('edit'):
            root_config["editorConfig"]["mode"] = "view"
            root_config["document"]["permissions"] = roll_access
        else:
            root_config["editorConfig"]["mode"] = "edit"
            root_config["document"]["permissions"] = roll_access

        if jwt_utils.is_jwt_enabled(request.env):
            root_config["token"] = jwt_utils.encode_payload(request.env, root_config)

        _logger.info("prepare_editor_values - success: %s", attachment.id)
        return {
            "docTitle": filename,
            "docIcon": f"/onlyoffice_odoo/static/description/editor_icons/{document_type}.ico",
            "docApiJS": docserver_url + "web-apps/apps/api/documents/api.js",
            "editorConfig": markupsafe.Markup(json.dumps(root_config)),
        }

    @http.route("/onlyoffice/editor/<int:attachment_id>/<int:readonly>", auth="public", type="http", website=True)
    def render_editor_read_only(self, attachment_id, readonly=0, access_token=None):
        _logger.info("GET /onlyoffice/editor/%s", attachment_id)
        attachment = self.get_attachment(attachment_id)
        if not attachment:
            _logger.warning("GET /onlyoffice/editor/%s - attachment not found", attachment_id)
            return request.not_found()

        attachment.validate_access(access_token)

        if attachment.res_model == "documents.document":
            document = request.env["documents.document"].browse(int(attachment.res_id))
            self._check_document_access(document)

        data = attachment.read(["id", "checksum", "public", "name", "access_token"])[0]
        filename = data["name"]

        can_read = attachment.check_access_rights("read", raise_exception=False) and file_utils.can_view(filename)
        can_write = attachment.check_access_rights("write", raise_exception=False) and file_utils.can_edit(filename)

        if readonly == 1:
            can_write = False
        if not can_read:
            _logger.warning("GET /onlyoffice/editor/%s - no read access", attachment_id)
            raise Exception("cant read")

        _logger.info("GET /onlyoffice/editor/%s - success", attachment_id)
        return request.render(
            "onlyoffice_odoo.onlyoffice_editor", self.prepare_editor_values(attachment, access_token, can_write)
        )

    @http.route(
        "/onlyoffice/editor/callback/<int:attachment_id>", auth="public", methods=["POST"], type="http", csrf=False
    )
    def editor_callback(self, attachment_id, oo_security_token=None, access_token=None):
        _logger.info("POST /onlyoffice/editor/callback/%s", attachment_id)
        response_json = {"error": 0}

        try:
            body = request.get_json_data()
            user = self.get_user_from_token(oo_security_token)
            attachment = self.get_attachment(attachment_id, user)
            if not attachment:
                _logger.warning("POST /onlyoffice/editor/callback/%s - attachment not found", attachment_id)
                raise Exception("attachment not found")

            attachment.validate_access(access_token)
            attachment.check_access_rights("write")

            if jwt_utils.is_jwt_enabled(request.env):
                token = body.get("token")

                if not token:
                    token = request.httprequest.headers.get(config_utils.get_jwt_header(request.env))
                    if token:
                        token = token[len("Bearer "):]

                if not token:
                    _logger.warning("POST /onlyoffice/editor/callback/%s - JWT token missing", attachment_id)
                    raise Exception("expected JWT")

                body = jwt_utils.decode_token(request.env, token)
                if body.get("payload"):
                    body = body["payload"]

            status = body["status"]
            _logger.info("POST /onlyoffice/editor/callback/%s - status: %s", attachment_id, status)

            if (status == 2) | (status == 3) | (status == 6):  # mustsave, corrupted
                file_url = url_utils.replace_public_url_to_internal(request.env, body.get("url"))
                datas = onlyoffice_urlopen(file_url).read()
                if attachment.res_model == "documents.document":
                    datas = base64.encodebytes(datas)
                    document = request.env["documents.document"].browse(int(attachment.res_id))
                    document.with_user(user).write(
                        {
                            "name": attachment.name,
                            "datas": datas,
                            "mimetype": guess_type(file_url)[0],
                        }
                    )

                    attachment_version = attachment.oo_attachment_version
                    attachment.write({"oo_attachment_version": attachment_version + 1})
                    previous_attachments = (
                        request.env["ir.attachment"]
                        .sudo()
                        .search(
                            [
                                ("res_model", "=", "documents.document"),
                                ("res_id", "=", document.id),
                                ("oo_attachment_version", "=", attachment_version),
                            ],
                            limit=1,
                        )
                    )
                    name = attachment.name
                    filename, ext = os.path.splitext(attachment.name)
                    name = f"{filename} ({attachment_version}){ext}"
                    previous_attachments.sudo().write({"name": name})
                else:
                    attachment.write({"raw": datas, "mimetype": guess_type(file_url)[0]})

                _logger.info("POST /onlyoffice/editor/callback/%s - file saved successfully", attachment_id)

        except Exception as ex:
            _logger.error("POST /onlyoffice/editor/callback/%s - error: %s", attachment_id, str(ex))
            response_json["error"] = 1
            response_json["message"] = http.serialize_exception(ex)

        return request.make_response(
            data=json.dumps(response_json),
            status=500 if response_json["error"] == 1 else 200,
            headers=[("Content-Type", "application/json")],
        )

    def prepare_editor_values(self, attachment, access_token, can_write):
        _logger.info("prepare_editor_values - attachment: %s", attachment.id)
        data = attachment.read(["id", "checksum", "public", "name", "access_token"])[0]
        key = str(data["id"]) + str(data["checksum"])
        docserver_url = config_utils.get_doc_server_public_url(request.env)
        odoo_url = config_utils.get_base_or_odoo_url(request.env)

        filename = self.filter_xss(data["name"])

        security_token = jwt_utils.encode_payload(
            request.env, {"id": request.env.user.id}, config_utils.get_internal_jwt_secret(request.env)
        )
        security_token = security_token.decode("utf-8") if isinstance(security_token, bytes) else security_token
        access_token = access_token.decode("utf-8") if isinstance(access_token, bytes) else access_token
        path_part = (
            str(data["id"])
            + "?oo_security_token="
            + security_token
            + ("&access_token=" + access_token if access_token else "")
            + "&shardkey="
            + key
        )

        document_type = file_utils.get_file_type(filename)

        is_mobile = bool(re.search(_mobile_regex, request.httprequest.headers.get("User-Agent"), re.IGNORECASE))

        root_config = {
            "width": "100%",
            "height": "100%",
            "type": "mobile" if is_mobile else "desktop",
            "documentType": document_type,
            "document": {
                "title": filename,
                "url": odoo_url + "onlyoffice/file/content/" + path_part,
                "fileType": file_utils.get_file_ext(filename),
                "key": key,
                "permissions": {},
            },
            "editorConfig": {
                "lang": request.env.user.lang,
                "user": {"id": str(request.env.user.id), "name": request.env.user.name},
                "customization": {
                    'autosave': True,
                    'forcesave': True,
                },

                'coEditing': {
                    'mode': "fast",
                    'change': False
                }
            },
        }

        if can_write:
            root_config["editorConfig"]["callbackUrl"] = odoo_url + "onlyoffice/editor/callback/" + path_part

        if attachment.res_model != "documents.document":
            root_config["editorConfig"]["mode"] = "edit" if can_write else "view"
            root_config["document"]["permissions"]["edit"] = can_write
        elif attachment.res_model == "documents.document":
            root_config = self.get_documents_permissions(attachment, can_write, root_config)

        if jwt_utils.is_jwt_enabled(request.env):
            root_config["token"] = jwt_utils.encode_payload(request.env, root_config)

        _logger.info("prepare_editor_values - success: %s", attachment.id)
        return {
            "docTitle": filename,
            "docIcon": f"/onlyoffice_odoo/static/description/editor_icons/{document_type}.ico",
            "docApiJS": docserver_url + "web-apps/apps/api/documents/api.js",
            "editorConfig": markupsafe.Markup(json.dumps(root_config)),
        }