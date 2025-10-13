##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################


import werkzeug.urls

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RequestApproval(models.TransientModel):
    _name = "request.approval"
    _description = "Request Approval"

    name = fields.Char(string="Title", required=True)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Medium"), ("2", "High"), ("3", "Very High")],
        default="0",
    )
    request_date = fields.Datetime(default=fields.Datetime.now, required=True)
    type_id = fields.Many2one(
        string="Type", comodel_name="multi.approval.type", required=True
    )
    description = fields.Html()
    origin_ref = fields.Reference(string="Origin", selection="_selection_target_model")

    @api.model
    def _selection_target_model(self):
        models = self.env["ir.model"].search([])
        return [(model.model, model.name) for model in models]

    def _get_obj_url(self, obj):
        base = "web#"
        fragment = {"view_type": "form", "model": obj._name, "id": obj.id}
        url = base + werkzeug.urls.url_encode(fragment)
        return "{base}/{url}".format(
            base=self.env["ir.config_parameter"].sudo().get_param("web.base.url"),
            url=url,
        )

    @api.model
    def default_get(self, fs):
        """
        1. Get approval type
        2. Set the title as document's name
        3. Set origin
        """
        res = super().default_get(fs)
        ctx = self._context
        model_name = ctx.get("active_model")
        res_id = ctx.get("active_id")
        types = self.env["multi.approval.type"]._get_types(model_name)
        approval_type = self.env["multi.approval.type"].filter_type(
            types, model_name, res_id
        )
        if not approval_type:
            # Retry
            approval_type = self.env["multi.approval.type"].filter_type(
                types, model_name, res_id, ignore_potential=True
            )
        if not approval_type:
            raise UserError(
                _("Data is changed! Please refresh your browser in order to continue !")
            )

        # Add the link to the source document inside the description.
        # in order to bypass the record rule on it
        record = self.env[model_name].browse(res_id)
        record_name = record.display_name or _("this object")
        title = _("Request approval for {}").format(record_name)
        record_url = self._get_obj_url(record)
        if approval_type.request_tmpl:
            request_tmpl = werkzeug.urls.url_unquote(_(approval_type.request_tmpl))
            descr = request_tmpl.format(
                record_url=record_url, record_name=record_name, record=record
            )
        else:
            descr = ""
        res.update(
            {
                "name": title,
                "type_id": approval_type.id,
                "origin_ref": f"{model_name},{res_id}",
                "description": descr,
            }
        )
        return res

    def action_request(self, return_request=False):
        """
        1. create request
        2. Submit request
        3. update x_has_request_approval = True
        4. open request form view
        """
        self.ensure_one()

        if (
            not self.type_id.active
            or not self.type_id.is_configured
            or not self.origin_ref.x_need_approval
        ):
            raise UserError(
                _("Data is changed! Please refresh your browser in order to continue !")
            )
        if self.origin_ref.x_has_request_approval and not self.type_id.is_free_create:
            raise UserError(_("Request has been created before !"))
        # create request
        vals = {
            "name": self.name,
            "priority": self.priority,
            "type_id": self.type_id.id,
            "description": self.description,
            "origin_ref": f"{self.origin_ref._name},{self.origin_ref.id}",
        }
        request = self.env["multi.approval"].create(vals)
        request.action_submit()

        # update x_has_request_approval
        self.env["multi.approval.type"].update_x_field(
            request.origin_ref, "x_has_request_approval"
        )
        # update x_potential_type_id
        self.env["multi.approval.type"].update_x_field(
            self.origin_ref, "x_potential_type_id", False, raise_if_not_exist=False
        )

        if return_request:
            return request

        return {
            "name": _("My Requests"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "multi.approval",
            "res_id": request.id,
        }
