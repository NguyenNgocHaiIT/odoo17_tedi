##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from lxml import etree

from odoo import api, models


class View(models.Model):
    _inherit = "ir.ui.view"

    @api.model
    def set_modified_invisible(self, ele, invi_dm):
        invisible = invi_dm
        if ele.get("invisible"):
            invisible = f"({ele.get('invisible')}) or ({invisible})"
        ele.set("invisible", invisible)

    @api.model
    def postprocess_and_fields(self, node, model=None, **options):
        """
        1. check if the view loads x_need_approval and x_review_result
        2. check if the approval type is working
        3. add/update the 'modifiers': invisible for the button
        """
        arch, fs = super().postprocess_and_fields(node, model, **options)
        if node.tag != "form":
            return arch, fs
        if "x_need_approval" not in fs.get(
            model, set()
        ) or "x_review_result" not in fs.get(model, set()):
            return arch, fs

        # Find the approval type
        approval_types = self.env["multi.approval.type"]._get_types(model)
        if not approval_types or all(not x.hide_button for x in approval_types):
            return arch, fs

        doc = etree.XML(arch)

        invi_dm = (
            "x_need_approval and (not x_review_result or x_review_result == 'refused')"
        )

        for btn in doc.xpath("//form//header//button"):
            if btn.get("approval_btn"):
                continue
            self.set_modified_invisible(btn, invi_dm)

        arch = etree.tostring(doc, encoding="unicode")
        return arch, fs
