##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import exceptions

from .base_configuration import ApprovalTestConfiguration


class ApprovalNextMoveTest(ApprovalTestConfiguration):
    def test_request_approval_auto(self):
        # Request approval
        request1 = self.request_one(self.obj_1, self.user_1)
        self.assertEqual(request1.type_id, self.approval_type_2)
        # To trigger type_3
        self.approval_type_2.approve_python_code = (
            'record.write({"state": "to_approve_2"})'
        )
        self.approval_type_2.next_move_ids = self.approval_type_3
        self.approval_type_2.next_move_policy = "auto"

        # Approve Request
        request1.with_user(self.approver_1).action_approve()
        request1.with_user(self.approver_2).action_approve()
        self.assertEqual(request1.state, "Approved")
        self.assertEqual(request1.origin_ref.state, "to_approve_2")
        self.assertTrue(request1.origin_ref.x_need_approval)
        self.assertFalse(request1.origin_ref.x_review_result)

        # New request
        origin_ref = f"{request1.origin_ref._name},{request1.origin_ref.id}"
        request2 = self.env[request1._name].search(
            [
                ("origin_ref", "=", origin_ref),
                ("type_id", "=", self.approval_type_3.id),
                ("state", "=", "Submitted"),
            ]
        )
        self.assertEqual(len(request2), 1)

        # Approve Request again
        request2.with_user(self.approver_1).action_approve()
        request2.with_user(self.approver_2).action_approve()
        self.assertEqual(request2.state, "Approved")
        self.assertEqual(request2.origin_ref.state, "approve")
        self.assertEqual(request2.origin_ref.x_review_result, "approved")

    def test_request_approval_manual(self):
        # Request approval
        request1 = self.request_one(self.obj_1, self.user_1)
        self.assertEqual(request1.type_id, self.approval_type_2)
        # To trigger type_3
        self.approval_type_2.approve_python_code = (
            'record.write({"state": "to_approve_2"})'
        )
        self.approval_type_2.next_move_ids = self.approval_type_3
        self.approval_type_2.next_move_policy = "manu"

        # Approve Request
        request1.with_user(self.approver_1).action_approve()
        request1.with_user(self.approver_2).action_approve()
        self.assertEqual(request1.state, "Approved")
        self.assertEqual(request1.origin_ref.state, "to_approve_2")
        self.assertTrue(request1.origin_ref.x_need_approval)
        self.assertFalse(request1.origin_ref.x_review_result)

        # Checks for next request
        self.assertFalse(request1.origin_ref.x_has_request_approval)
        self.assertEqual(
            request1.origin_ref.x_potential_type_id, self.approval_type_3.id
        )

        # New request
        origin_ref = f"{request1.origin_ref._name},{request1.origin_ref.id}"
        request2 = self.env[request1._name].search(
            [
                ("origin_ref", "=", origin_ref),
                ("type_id", "=", self.approval_type_3.id),
                ("state", "=", "Submitted"),
            ]
        )
        self.assertFalse(request2)
        next_request = self.request_one(self.obj_1, self.user_1)
        self.assertEqual(next_request.type_id, self.approval_type_3)
        self.assertTrue(request1.origin_ref.x_has_request_approval)
        self.assertFalse(request1.origin_ref.x_potential_type_id)

        # Approve Request again
        next_request.with_user(self.approver_1).action_approve()
        next_request.with_user(self.approver_2).action_approve()
        self.assertEqual(next_request.state, "Approved")
        self.assertEqual(next_request.origin_ref.state, "approve")
        self.assertEqual(next_request.origin_ref.x_review_result, "approved")

    def test_request_approval_manual_stage_change(self):
        """
        After seting the next move on related document. Because of any reason,
        the record does not meet the domain of the next move.
        Do remove the value of next move from related document
        """
        # Request approval
        request1 = self.request_one(self.obj_1, self.user_1)
        # To trigger type_3
        self.approval_type_2.approve_python_code = (
            'record.write({"state": "to_approve_2"})'
        )
        self.approval_type_2.next_move_ids = self.approval_type_3
        self.approval_type_2.next_move_policy = "manu"

        # Approve Request
        request1.with_user(self.approver_1).action_approve()
        request1.with_user(self.approver_2).action_approve()

        # changes state
        self.assertTrue(self.obj_1.x_need_approval)
        self.obj_1.with_context(run_python_code=1).state = "approve"
        x_need_approval = self.env["multi.approval.type"].compute_need_approval(
            self.obj_1
        )
        self.assertFalse(x_need_approval)

        # New request
        with self.assertRaises(exceptions.UserError):
            self.request_one(self.obj_1, self.user_1)
