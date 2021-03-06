#!/usr/bin/env python
"""This module contains regression tests for user API handlers."""



from grr.gui import api_regression_test_lib
from grr.gui.api_plugins import user as user_plugin

from grr.lib import access_control
from grr.lib import aff4
from grr.lib import flags
from grr.lib import flow
from grr.lib import rdfvalue
from grr.lib import test_lib
from grr.lib.aff4_objects import cronjobs as aff4_cronjobs

from grr.lib.aff4_objects import security
from grr.lib.aff4_objects import users as aff4_users

from grr.lib.hunts import implementation
from grr.lib.hunts import standard
from grr.lib.hunts import standard_test


class ApiGetClientApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGetClientApprovalHandler."""

  api_method = "GetClientApproval"
  handler = user_plugin.ApiGetClientApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("approver")

      clients = self.SetupClients(2)
      for client_id in clients:
        # Delete the certificate as it's being regenerated every time the
        # client is created.
        with aff4.FACTORY.Open(
            client_id, mode="rw", token=self.token) as grr_client:
          grr_client.DeleteAttribute(grr_client.Schema.CERT)

    with test_lib.FakeTime(44):
      flow_urn = flow.GRRFlow.StartFlow(
          client_id=clients[0],
          flow_name=security.RequestClientApprovalFlow.__name__,
          reason="foo",
          subject_urn=clients[0],
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval1_id = flow_fd.state.approval_id

    with test_lib.FakeTime(45):
      flow_urn = flow.GRRFlow.StartFlow(
          client_id=clients[1],
          flow_name=security.RequestClientApprovalFlow.__name__,
          reason="bar",
          subject_urn=clients[1],
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval2_id = flow_fd.state.approval_id

    with test_lib.FakeTime(84):
      approver_token = access_control.ACLToken(username="approver")
      flow.GRRFlow.StartFlow(
          client_id=clients[1],
          flow_name=security.GrantClientApprovalFlow.__name__,
          reason="bar",
          delegate=self.token.username,
          subject_urn=clients[1],
          token=approver_token)

    with test_lib.FakeTime(126):
      self.Check(
          "GetClientApproval",
          args=user_plugin.ApiGetClientApprovalArgs(
              client_id=clients[0].Basename(),
              approval_id=approval1_id,
              username=self.token.username),
          replace={approval1_id: "approval:111111"})
      self.Check(
          "GetClientApproval",
          args=user_plugin.ApiGetClientApprovalArgs(
              client_id=clients[1].Basename(),
              approval_id=approval2_id,
              username=self.token.username),
          replace={approval2_id: "approval:222222"})


class ApiGrantClientApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGrantClientApprovalHandler."""

  api_method = "GrantClientApproval"
  handler = user_plugin.ApiGrantClientApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("requestor")

      clients = self.SetupClients(1)
      for client_id in clients:
        # Delete the certificate as it's being regenerated every time the
        # client is created.
        with aff4.FACTORY.Open(
            client_id, mode="rw", token=self.token) as grr_client:
          grr_client.DeleteAttribute(grr_client.Schema.CERT)

    with test_lib.FakeTime(44):
      requestor_token = access_control.ACLToken(username="requestor")
      flow_urn = flow.GRRFlow.StartFlow(
          client_id=clients[0],
          flow_name=security.RequestClientApprovalFlow.__name__,
          reason="foo",
          subject_urn=clients[0],
          approver=self.token.username,
          token=requestor_token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval_id = flow_fd.state.approval_id

    with test_lib.FakeTime(126):
      self.Check(
          "GrantClientApproval",
          args=user_plugin.ApiGrantClientApprovalArgs(
              client_id=clients[0].Basename(),
              approval_id=approval_id,
              username="requestor"),
          replace={approval_id: "approval:111111"})


class ApiCreateClientApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiCreateClientApprovalHandler."""

  api_method = "CreateClientApproval"
  handler = user_plugin.ApiCreateClientApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateUser("approver")

      client_id = self.SetupClients(1)[0]

      # Delete the certificate as it's being regenerated every time the
      # client is created.
      with aff4.FACTORY.Open(
          client_id, mode="rw", token=self.token) as grr_client:
        grr_client.DeleteAttribute(grr_client.Schema.CERT)

    def ReplaceApprovalId():
      approvals = list(
          aff4.FACTORY.ListChildren(
              aff4.ROOT_URN.Add("ACL").Add(client_id.Basename()).Add(
                  self.token.username),
              token=self.token))

      return {approvals[0].Basename(): "approval:112233"}

    with test_lib.FakeTime(126):
      self.Check(
          "CreateClientApproval",
          args=user_plugin.ApiCreateClientApprovalArgs(
              client_id=client_id.Basename(),
              approval=user_plugin.ApiClientApproval(
                  reason="really important reason!",
                  notified_users=["approver1", "approver2"],
                  email_cc_addresses=["test@example.com"])),
          replace=ReplaceApprovalId)


class ApiListClientApprovalsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiListClientApprovalsHandlerTest."""

  api_method = "ListClientApprovals"
  handler = user_plugin.ApiListClientApprovalsHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("approver")

      clients = self.SetupClients(2)
      for client_id in clients:
        # Delete the certificate as it's being regenerated every time the
        # client is created.
        with aff4.FACTORY.Open(
            client_id, mode="rw", token=self.token) as grr_client:
          grr_client.DeleteAttribute(grr_client.Schema.CERT)

    with test_lib.FakeTime(44):
      flow_urn = flow.GRRFlow.StartFlow(
          client_id=clients[0],
          flow_name=security.RequestClientApprovalFlow.__name__,
          reason=self.token.reason,
          subject_urn=clients[0],
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval1_id = flow_fd.state.approval_id

    with test_lib.FakeTime(45):
      flow_urn = flow.GRRFlow.StartFlow(
          client_id=clients[1],
          flow_name=security.RequestClientApprovalFlow.__name__,
          reason=self.token.reason,
          subject_urn=clients[1],
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval2_id = flow_fd.state.approval_id

    with test_lib.FakeTime(84):
      approver_token = access_control.ACLToken(username="approver")
      flow.GRRFlow.StartFlow(
          client_id=clients[1],
          flow_name=security.GrantClientApprovalFlow.__name__,
          reason=self.token.reason,
          delegate=self.token.username,
          subject_urn=clients[1],
          token=approver_token)

    with test_lib.FakeTime(126):
      self.Check(
          "ListClientApprovals",
          args=user_plugin.ApiListClientApprovalsArgs(),
          replace={
              approval1_id: "approval:111111",
              approval2_id: "approval:222222"
          })
      self.Check(
          "ListClientApprovals",
          args=user_plugin.ApiListClientApprovalsArgs(
              client_id=clients[0].Basename()),
          replace={
              approval1_id: "approval:111111",
              approval2_id: "approval:222222"
          })


class ApiGetHuntApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    standard_test.StandardHuntTestMixin):
  """Regression test for ApiGetHuntApprovalHandler."""

  api_method = "GetHuntApproval"
  handler = user_plugin.ApiGetHuntApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("approver")

      with self.CreateHunt(description="hunt1") as hunt_obj:
        hunt1_urn = hunt_obj.urn
        hunt1_id = hunt1_urn.Basename()

      with self.CreateHunt(description="hunt2") as hunt_obj:
        hunt2_urn = hunt_obj.urn
        hunt2_id = hunt2_urn.Basename()

    with test_lib.FakeTime(44):
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestHuntApprovalFlow.__name__,
          reason="foo",
          subject_urn=hunt1_urn,
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval1_id = flow_fd.state.approval_id

    with test_lib.FakeTime(45):
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestHuntApprovalFlow.__name__,
          reason="bar",
          subject_urn=hunt2_urn,
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval2_id = flow_fd.state.approval_id

    with test_lib.FakeTime(84):
      approver_token = access_control.ACLToken(username="approver")
      flow.GRRFlow.StartFlow(
          flow_name=security.GrantHuntApprovalFlow.__name__,
          reason="bar",
          delegate=self.token.username,
          subject_urn=hunt2_urn,
          token=approver_token)

    with test_lib.FakeTime(126):
      self.Check(
          "GetHuntApproval",
          args=user_plugin.ApiGetHuntApprovalArgs(
              username=self.token.username,
              hunt_id=hunt1_id,
              approval_id=approval1_id),
          replace={hunt1_id: "H:123456",
                   approval1_id: "approval:111111"})
      self.Check(
          "GetHuntApproval",
          args=user_plugin.ApiGetHuntApprovalArgs(
              username=self.token.username,
              hunt_id=hunt2_id,
              approval_id=approval2_id),
          replace={hunt2_id: "H:567890",
                   approval2_id: "approval:222222"})


class ApiGrantHuntApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    standard_test.StandardHuntTestMixin):
  """Regression test for ApiGrantHuntApprovalHandler."""

  api_method = "GrantHuntApproval"
  handler = user_plugin.ApiGrantHuntApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("requestor")

      with self.CreateHunt(description="a hunt") as hunt_obj:
        hunt_urn = hunt_obj.urn
        hunt_id = hunt_urn.Basename()

    with test_lib.FakeTime(44):
      requestor_token = access_control.ACLToken(username="requestor")
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestHuntApprovalFlow.__name__,
          reason="foo",
          subject_urn=hunt_urn,
          approver=self.token.username,
          token=requestor_token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval_id = flow_fd.state.approval_id

    with test_lib.FakeTime(126):
      self.Check(
          "GrantHuntApproval",
          args=user_plugin.ApiGrantHuntApprovalArgs(
              hunt_id=hunt_id, approval_id=approval_id, username="requestor"),
          replace={hunt_id: "H:123456",
                   approval_id: "approval:111111"})


class ApiCreateHuntApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    standard_test.StandardHuntTestMixin):
  """Regression test for ApiCreateHuntApprovalHandler."""

  api_method = "CreateHuntApproval"
  handler = user_plugin.ApiCreateHuntApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateUser("approver")

      with self.CreateHunt(description="foo") as hunt_obj:
        hunt_id = hunt_obj.urn.Basename()

    def ReplaceHuntAndApprovalIds():
      approvals = list(
          aff4.FACTORY.ListChildren(
              aff4.ROOT_URN.Add("ACL").Add("hunts").Add(hunt_id).Add(
                  self.token.username),
              token=self.token))

      return {approvals[0].Basename(): "approval:112233", hunt_id: "H:123456"}

    with test_lib.FakeTime(126):
      self.Check(
          "CreateHuntApproval",
          args=user_plugin.ApiCreateHuntApprovalArgs(
              hunt_id=hunt_id,
              approval=user_plugin.ApiHuntApproval(
                  reason="really important reason!",
                  notified_users=["approver1", "approver2"],
                  email_cc_addresses=["test@example.com"])),
          replace=ReplaceHuntAndApprovalIds)


class ApiListHuntApprovalsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiListClientApprovalsHandlerTest."""

  api_method = "ListHuntApprovals"
  handler = user_plugin.ApiListHuntApprovalsHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("approver")

      hunt = implementation.GRRHunt.StartHunt(
          hunt_name=standard.GenericHunt.__name__, token=self.token)

    with test_lib.FakeTime(43):
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestHuntApprovalFlow.__name__,
          reason=self.token.reason,
          subject_urn=hunt.urn,
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval_id = flow_fd.state.approval_id

    with test_lib.FakeTime(126):
      self.Check(
          "ListHuntApprovals",
          replace={
              hunt.urn.Basename(): "H:123456",
              approval_id: "approval:112233"
          })


class ApiGetCronJobApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGetCronJobApprovalHandler."""

  api_method = "GetCronJobApproval"
  handler = user_plugin.ApiGetCronJobApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("approver")

      cron_manager = aff4_cronjobs.CronManager()
      cron_args = aff4_cronjobs.CreateCronJobFlowArgs(
          periodicity="1d", allow_overruns=False)
      cron1_urn = cron_manager.ScheduleFlow(
          cron_args=cron_args, token=self.token)
      cron2_urn = cron_manager.ScheduleFlow(
          cron_args=cron_args, token=self.token)

    with test_lib.FakeTime(44):
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestCronJobApprovalFlow.__name__,
          reason="foo",
          subject_urn=cron1_urn,
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval1_id = flow_fd.state.approval_id

    with test_lib.FakeTime(45):
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestCronJobApprovalFlow.__name__,
          reason="bar",
          subject_urn=cron2_urn,
          approver="approver",
          token=self.token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval2_id = flow_fd.state.approval_id

    with test_lib.FakeTime(84):
      approver_token = access_control.ACLToken(username="approver")
      flow.GRRFlow.StartFlow(
          flow_name=security.GrantCronJobApprovalFlow.__name__,
          reason="bar",
          delegate=self.token.username,
          subject_urn=cron2_urn,
          token=approver_token)

    with test_lib.FakeTime(126):
      self.Check(
          "GetCronJobApproval",
          args=user_plugin.ApiGetCronJobApprovalArgs(
              username=self.token.username,
              cron_job_id=cron1_urn.Basename(),
              approval_id=approval1_id),
          replace={
              cron1_urn.Basename(): "CronJob_123456",
              approval1_id: "approval:111111"
          })
      self.Check(
          "GetCronJobApproval",
          args=user_plugin.ApiGetCronJobApprovalArgs(
              username=self.token.username,
              cron_job_id=cron2_urn.Basename(),
              approval_id=approval2_id),
          replace={
              cron2_urn.Basename(): "CronJob_567890",
              approval2_id: "approval:222222"
          })


class ApiGrantCronJobApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGrantCronJobApprovalHandler."""

  api_method = "GrantCronJobApproval"
  handler = user_plugin.ApiGrantCronJobApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateAdminUser("requestor")

      cron_manager = aff4_cronjobs.CronManager()
      cron_args = aff4_cronjobs.CreateCronJobFlowArgs(
          periodicity="1d", allow_overruns=False)
      cron_urn = cron_manager.ScheduleFlow(
          cron_args=cron_args, token=self.token)

    with test_lib.FakeTime(44):
      requestor_token = access_control.ACLToken(username="requestor")
      flow_urn = flow.GRRFlow.StartFlow(
          flow_name=security.RequestCronJobApprovalFlow.__name__,
          reason="foo",
          subject_urn=cron_urn,
          approver=self.token.username,
          token=requestor_token)
      flow_fd = aff4.FACTORY.Open(
          flow_urn, aff4_type=flow.GRRFlow, token=self.token)
      approval_id = flow_fd.state.approval_id

    with test_lib.FakeTime(126):
      self.Check(
          "GrantCronJobApproval",
          args=user_plugin.ApiGrantCronJobApprovalArgs(
              cron_job_id=cron_urn.Basename(),
              approval_id=approval_id,
              username="requestor"),
          replace={
              cron_urn.Basename(): "CronJob_123456",
              approval_id: "approval:111111"
          })


class ApiCreateCronJobApprovalHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiCreateCronJobApprovalHandler."""

  api_method = "CreateCronJobApproval"
  handler = user_plugin.ApiCreateCronJobApprovalHandler

  def Run(self):
    with test_lib.FakeTime(42):
      self.CreateUser("approver")

    cron_manager = aff4_cronjobs.CronManager()
    cron_args = aff4_cronjobs.CreateCronJobFlowArgs(
        periodicity="1d", allow_overruns=False)
    cron_urn = cron_manager.ScheduleFlow(cron_args=cron_args, token=self.token)
    cron_id = cron_urn.Basename()

    def ReplaceCronAndApprovalIds():
      approvals = list(
          aff4.FACTORY.ListChildren(
              aff4.ROOT_URN.Add("ACL").Add("cron").Add(cron_id).Add(
                  self.token.username),
              token=self.token))

      return {
          approvals[0].Basename(): "approval:112233",
          cron_id: "CronJob_123456"
      }

    with test_lib.FakeTime(126):
      self.Check(
          "CreateCronJobApproval",
          args=user_plugin.ApiCreateCronJobApprovalArgs(
              cron_job_id=cron_id,
              approval=user_plugin.ApiCronJobApproval(
                  reason="really important reason!",
                  notified_users=["approver1", "approver2"],
                  email_cc_addresses=["test@example.com"])),
          replace=ReplaceCronAndApprovalIds)


class ApiGetGrrUserHandlerRegresstionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGetUserSettingsHandler."""

  api_method = "GetGrrUser"
  handler = user_plugin.ApiGetGrrUserHandler

  def Run(self):
    with test_lib.FakeTime(42):
      with aff4.FACTORY.Create(
          aff4.ROOT_URN.Add("users").Add(self.token.username),
          aff4_type=aff4_users.GRRUser,
          mode="w",
          token=self.token) as user_fd:
        user_fd.Set(
            user_fd.Schema.GUI_SETTINGS,
            aff4_users.GUISettings(canary_mode=True))

    self.Check("GetGrrUser")


class ApiGetPendingUserNotificationsCountHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiGetPendingUserNotificationsCountHandler."""

  api_method = "GetPendingUserNotificationsCount"
  handler = user_plugin.ApiGetPendingUserNotificationsCountHandler

  def setUp(self):
    super(ApiGetPendingUserNotificationsCountHandlerRegressionTest,
          self).setUp()
    self.client_id = self.SetupClients(1)[0]

  def Run(self):
    self._SendNotification(
        notification_type="Discovery",
        subject="<some client urn>",
        message="<some message>",
        client_id=self.client_id)
    self._SendNotification(
        notification_type="ViewObject",
        subject=str(self.client_id),
        message="<some other message>",
        client_id=self.client_id)

    self.Check("GetPendingUserNotificationsCount")


class ApiListPendingUserNotificationsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiListPendingUserNotificationsHandler."""

  api_method = "ListPendingUserNotifications"
  handler = user_plugin.ApiListPendingUserNotificationsHandler

  def setUp(self):
    super(ApiListPendingUserNotificationsHandlerRegressionTest, self).setUp()
    self.client_id = self.SetupClients(1)[0]

  def Run(self):
    with test_lib.FakeTime(42):
      self._SendNotification(
          notification_type="Discovery",
          subject=str(self.client_id),
          message="<some message>",
          client_id=self.client_id)

    with test_lib.FakeTime(44):
      self._SendNotification(
          notification_type="ViewObject",
          subject=str(self.client_id),
          message="<some other message>",
          client_id=self.client_id)

    self.Check(
        "ListPendingUserNotifications",
        args=user_plugin.ApiListPendingUserNotificationsArgs())
    self.Check(
        "ListPendingUserNotifications",
        args=user_plugin.ApiListPendingUserNotificationsArgs(
            timestamp=43000000))


class ApiListAndResetUserNotificationsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiListAndResetUserNotificationsHandler."""

  api_method = "ListAndResetUserNotifications"
  handler = user_plugin.ApiListAndResetUserNotificationsHandler

  def setUp(self):
    super(ApiListAndResetUserNotificationsHandlerRegressionTest, self).setUp()
    self.client_id = self.SetupClients(1)[0]

  def Run(self):
    with test_lib.FakeTime(42):
      self._SendNotification(
          notification_type="Discovery",
          subject=str(self.client_id),
          message="<some message>",
          client_id=self.client_id)

    with test_lib.FakeTime(44):
      self._SendNotification(
          notification_type="ViewObject",
          subject=str(self.client_id),
          message="<some other message>",
          client_id=self.client_id)

    # Notifications are pending in this request.
    self.Check(
        "ListAndResetUserNotifications",
        args=user_plugin.ApiListAndResetUserNotificationsArgs())

    # But not anymore in these requests.
    self.Check(
        "ListAndResetUserNotifications",
        args=user_plugin.ApiListAndResetUserNotificationsArgs(
            offset=1, count=1))
    self.Check(
        "ListAndResetUserNotifications",
        args=user_plugin.ApiListAndResetUserNotificationsArgs(filter="other"))


class ApiListPendingGlobalNotificationsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Regression test for ApiListPendingGlobalNotificationsHandler."""

  api_method = "ListPendingGlobalNotifications"
  handler = user_plugin.ApiListPendingGlobalNotificationsHandler

  # Global notifications are only shown in a certain time interval. By default,
  # this is from the moment they are created until two weeks later. Create
  # a notification that is too old to be returned and two valid ones.
  NOW = rdfvalue.RDFDatetime.Now()
  TIME_TOO_EARLY = NOW - rdfvalue.Duration("4w")
  TIME_0 = NOW - rdfvalue.Duration("12h")
  TIME_1 = NOW - rdfvalue.Duration("1h")

  def setUp(self):
    super(ApiListPendingGlobalNotificationsHandlerRegressionTest, self).setUp()

  def Run(self):
    with aff4.FACTORY.Create(
        aff4_users.GlobalNotificationStorage.DEFAULT_PATH,
        aff4_type=aff4_users.GlobalNotificationStorage,
        mode="rw",
        token=self.token) as storage:
      storage.AddNotification(
          aff4_users.GlobalNotification(
              type=aff4_users.GlobalNotification.Type.ERROR,
              header="Oh no, we're doomed!",
              content="Houston, Houston, we have a prob...",
              link="http://www.google.com",
              show_from=self.TIME_0))

      storage.AddNotification(
          aff4_users.GlobalNotification(
              type=aff4_users.GlobalNotification.Type.INFO,
              header="Nothing to worry about!",
              link="http://www.google.com",
              show_from=self.TIME_1))

      storage.AddNotification(
          aff4_users.GlobalNotification(
              type=aff4_users.GlobalNotification.Type.WARNING,
              header="Nothing to worry, we won't see this!",
              link="http://www.google.com",
              show_from=self.TIME_TOO_EARLY))

    replace = {
        ("%d" % self.TIME_0.AsMicroSecondsFromEpoch()): "0",
        ("%d" % self.TIME_1.AsMicroSecondsFromEpoch()): "0"
    }

    self.Check("ListPendingGlobalNotifications", replace=replace)


def main(argv):
  api_regression_test_lib.main(argv)


if __name__ == "__main__":
  flags.StartMain(main)
