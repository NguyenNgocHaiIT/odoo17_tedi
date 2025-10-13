##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from .base_configuration import ApprovalTestConfiguration


class SendRequestAuto(ApprovalTestConfiguration):
    def test_request_auto(self):
        self.approval_type_2.auto_request = True
        self.approval_type_2.auto_request_partner_ids = (
            self.user_2.partner_id | self.user_3.partner_id
        )
        self.approval_type_2.auto_request_follower_python_code = (
            "record.user_id.partner_id"
        )
        self.env["multi.approval.type"].cron_send_request()
        request = self.env["multi.approval"].search(
            [("name", "=", f"Request approval for {self.obj_1.name}")]
        )
        self.assertEqual(len(request), 1)
        self.assertTrue(self.user_3.partner_id in request.message_partner_ids)
        self.assertTrue(self.user_2.partner_id in request.message_partner_ids)
        self.assertTrue(self.user_1.partner_id in request.message_partner_ids)

        # Check rule
        request_count = (
            self.env["multi.approval"]
            .with_user(self.user_1)
            .search([("id", "=", request.id)])
        )
        self.assertEqual(len(request_count), 1)
        request_count = (
            self.env["multi.approval"]
            .with_user(self.user_2)
            .search([("id", "=", request.id)])
        )
        self.assertEqual(len(request_count), 1)
