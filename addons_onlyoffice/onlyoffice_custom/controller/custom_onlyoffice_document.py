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
                "customization": {},
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
