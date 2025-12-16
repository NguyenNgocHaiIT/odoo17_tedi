# -*- coding: utf-8 -*-
import json
import base64
from werkzeug.urls import url_decode

from odoo import http
from odoo.http import request, route, serialize_exception as _serialize_exception
from odoo.tools import html_escape

from odoo.addons.alnas_docx.controllers.report_controller import DocxReportController
from odoo.addons.alnas_xlsx.controllers.report_controller import XlsxReportController


class ReportDocxPreviewController(DocxReportController):

    @route("/report/docx_preview", type="json", auth="user")
    def docx_preview(self, **kwargs):
        try:
            req = json.loads(kwargs.get("data"))
            url, report_type = req[0], req[1]
            context = kwargs.get("context")

            if report_type != "docx":
                return {"error": "Invalid report type"}

            path = url.split("/report/docx/")[1]
            reportname, _, query = path.partition("?")
            docids = None

            if "/" in reportname:
                reportname, docids = reportname.split("/", 1)

            params = dict(url_decode(query).items()) if query else {}

            if "context" in params:
                base = json.loads(context or "{}")
                extra = json.loads(params.pop("context"))
                context = json.dumps({**base, **extra})

            response = self.report_routes(reportname, docids=docids, converter="docx", context=context, **params)

            report = request.env["ir.actions.report"]._get_report_from_name(reportname)
            filename = self._get_filename_by_report_type(report, report.name)

            obj = None
            if docids:
                ids = [int(x) for x in docids.split(",")]
                obj = request.env[report.model].browse(ids)

            attachment = request.env["ir.attachment"].create({
                "name": filename,
                "datas": base64.b64encode(response.data).decode(),
                "res_model": report.model,
                "res_id": obj.id if obj else 0,
                "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            })

            preview_rec = request.env["report.preview"].create({
                "name": filename,
                "action_report_id": report.id,
                "attachment_ids": [(6, 0, [attachment.id])],
            })

            return {
                "action": {
                    "type": "ir.actions.act_window",
                    "name": "Report Preview",
                    "res_model": "report.preview",
                    "res_id": preview_rec.id,
                    "view_mode": "form",
                    "views": [[False, "form"]],
                    "target": "new",
                }
            }

        except Exception as e:
            err = _serialize_exception(e)
            return request.make_response(html_escape(json.dumps({
                "code": 200,
                "message": "Odoo Server Error",
                "data": err
            })))


class ReportXlsxPreviewController(XlsxReportController):

    @route("/report/xlsx_preview", type="json", auth="user")
    def xlsx_preview(self, **kwargs):
        try:
            req = json.loads(kwargs.get("data"))
            url, report_type = req[0], req[1]
            context = kwargs.get("context")

            if report_type != "xlsx-jinja":
                return {"error": "Invalid report type"}

            reportname = url.split("/report/xlsx-jinja/")[1].split("?")[0]
            docids = None
            if "/" in reportname:
                reportname, docids = reportname.split("/")
            if docids:
                response = self.report_routes(
                    reportname, docids=docids, converter="xlsx-jinja", context=context
                )
            else:
                data = dict(url_decode(url.split("?")[1]).items())
                if "context" in data:
                    context, data_context = json.loads(context or "{}"), json.loads(data.pop("context"))
                    context = json.dumps({**context, **data_context})
                response = self.report_routes(
                    reportname, docids=docids, converter="xlsx-jinja", context=context, **data)

            report = request.env["ir.actions.report"]._get_report_from_name(reportname)
            filename = "%s.%s" % (reportname, "xlsx")

            if docids:
                ids = [int(x) for x in docids.split(",")]
                obj = request.env[report.model].browse(ids)

            attachment = request.env["ir.attachment"].create({
                "name": filename,
                "datas": base64.b64encode(response.data).decode(),
                "res_model": report.model,
                "res_id": obj.id if obj else 0,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            })

            preview_rec = request.env["report.preview"].create({
                "name": filename,
                "action_report_id": report.id,
                "attachment_ids": [(6, 0, [attachment.id])],
            })

            return {
                "action": {
                    "type": "ir.actions.act_window",
                    "name": "Report Preview",
                    "res_model": "report.preview",
                    "res_id": preview_rec.id,
                    "view_mode": "form",
                    "views": [[False, "form"]],
                    "target": "new",
                }
            }

        except Exception as e:
            err = _serialize_exception(e)
            return request.make_response(html_escape(json.dumps({
                "code": 200,
                "message": "Odoo Server Error",
                "data": err
            })))
