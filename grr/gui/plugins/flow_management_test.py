#!/usr/bin/env python
"""Test the flow_management interface."""


import os


from grr.gui import gui_test_lib
from grr.gui import runtests_test

from grr.lib import action_mocks
from grr.lib import aff4
from grr.lib import flags
from grr.lib import flow
from grr.lib import test_lib
from grr.lib.flows.general import filesystem as flows_filesystem
from grr.lib.flows.general import processes as flows_processes
from grr.lib.flows.general import transfer as flows_transfer
from grr.lib.flows.general import webhistory as flows_webhistory
from grr.lib.hunts import implementation
from grr.lib.hunts import standard
from grr.lib.hunts import standard_test
from grr.lib.rdfvalues import client as rdf_client
from grr.lib.rdfvalues import flows as rdf_flows
from grr.lib.rdfvalues import paths as rdf_paths


class TestFlowManagement(gui_test_lib.GRRSeleniumTest,
                         standard_test.StandardHuntTestMixin):
  """Test the flow management GUI."""

  def setUp(self):
    super(TestFlowManagement, self).setUp()

    self.client_id = rdf_client.ClientURN("C.0000000000000001")
    with aff4.FACTORY.Open(
        self.client_id, mode="rw", token=self.token) as client:
      client.Set(client.Schema.HOSTNAME("HostC.0000000000000001"))
    self.RequestAndGrantClientApproval(self.client_id)
    self.action_mock = action_mocks.FileFinderClientMock()

  def testOpeningManageFlowsOfUnapprovedClientRedirectsToHostInfoPage(self):
    self.Open("/#/clients/C.0000000000000002/flows/")

    # As we don't have an approval for C.0000000000000002, we should be
    # redirected to the host info page.
    self.WaitUntilEqual("/#/clients/C.0000000000000002/host-info",
                        self.GetCurrentUrlPath)
    self.WaitUntil(self.IsTextPresent,
                   "You do not have an approval for this client.")

  def testPageTitleReflectsSelectedFlow(self):
    pathspec = rdf_paths.PathSpec(
        path=os.path.join(self.base_path, "test.plist"),
        pathtype=rdf_paths.PathSpec.PathType.OS)
    flow_urn = flow.GRRFlow.StartFlow(
        flow_name=flows_transfer.GetFile.__name__,
        client_id=self.client_id,
        pathspec=pathspec,
        token=self.token)

    self.Open("/#/clients/C.0000000000000001/flows/")
    self.WaitUntilEqual("GRR | C.0000000000000001 | Flows", self.GetPageTitle)

    self.Click("css=td:contains('GetFile')")
    self.WaitUntilEqual("GRR | C.0000000000000001 | " + flow_urn.Basename(),
                        self.GetPageTitle)

  def testFlowManagement(self):
    """Test that scheduling flows works."""
    self.Open("/")

    self.Type("client_query", "C.0000000000000001")
    self.Click("client_query_submit")

    self.WaitUntilEqual(u"C.0000000000000001", self.GetText,
                        "css=span[type=subject]")

    # Choose client 1
    self.Click("css=td:contains('0001')")

    # First screen should be the Host Information already.
    self.WaitUntil(self.IsTextPresent, "HostC.0000000000000001")

    self.Click("css=a[grrtarget='client.launchFlows']")
    self.Click("css=#_Processes")
    self.Click("link=" + flows_processes.ListProcesses.__name__)
    self.WaitUntil(self.IsTextPresent, "C.0000000000000001")

    self.WaitUntil(self.IsTextPresent, "List running processes on a system.")

    self.Click("css=button.Launch")
    self.WaitUntil(self.IsTextPresent, "Launched Flow ListProcesses")

    self.Click("css=#_Browser")
    # Wait until the tree has expanded.
    self.WaitUntil(self.IsTextPresent, flows_webhistory.FirefoxHistory.__name__)

    # Check that we can get a file in chinese
    self.Click("css=#_Filesystem")

    # Wait until the tree has expanded.
    self.WaitUntil(self.IsTextPresent,
                   flows_filesystem.UpdateSparseImageChunks.__name__)

    self.Click("link=" + flows_transfer.GetFile.__name__)

    self.Select("css=.form-group:has(> label:contains('Pathtype')) select",
                "OS")
    self.Type("css=.form-group:has(> label:contains('Path')) input",
              u"/dev/c/msn[1].exe")

    self.Click("css=button.Launch")

    self.WaitUntil(self.IsTextPresent, "Launched Flow GetFile")

    # Test that recursive tests are shown in a tree table.
    flow.GRRFlow.StartFlow(
        client_id="aff4:/C.0000000000000001",
        flow_name=gui_test_lib.RecursiveTestFlow.__name__,
        token=self.token)

    self.Click("css=a[grrtarget='client.flows']")

    # Some rows are present in the DOM but hidden because parent flow row
    # wasn't expanded yet. Due to this, we have to explicitly filter rows
    # with "visible" jQuery filter.
    self.WaitUntilEqual(gui_test_lib.RecursiveTestFlow.__name__, self.GetText,
                        "css=grr-client-flows-list tr:visible:nth(1) td:nth(2)")

    self.WaitUntilEqual(flows_transfer.GetFile.__name__, self.GetText,
                        "css=grr-client-flows-list tr:visible:nth(2) td:nth(2)")

    # Click on the first tree_closed to open it.
    self.Click("css=grr-client-flows-list tr:visible:nth(1) .tree_closed")

    self.WaitUntilEqual(gui_test_lib.RecursiveTestFlow.__name__, self.GetText,
                        "css=grr-client-flows-list tr:visible:nth(2) td:nth(2)")

    # Select the requests tab
    self.Click("css=td:contains(GetFile)")
    self.Click("css=li[heading=Requests]")

    self.WaitUntil(self.IsElementPresent, "css=td:contains(1)")

    # Check that a StatFile client action was issued as part of the GetFile
    # flow.
    self.WaitUntil(self.IsElementPresent,
                   "css=.tab-content td.proto_value:contains(StatFile)")

  def testOverviewIsShownForNestedFlows(self):
    for _ in test_lib.TestFlowHelper(
        gui_test_lib.RecursiveTestFlow.__name__,
        self.action_mock,
        client_id=self.client_id,
        token=self.token):
      pass

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")

    # There should be a RecursiveTestFlow in the list. Expand nested flows.
    self.Click("css=tr:contains('RecursiveTestFlow') span.tree_branch")
    # Click on a nested flow.
    self.Click("css=tr:contains('RecursiveTestFlow'):nth(2)")

    # Nested flow should have Depth argument set to 1.
    self.WaitUntil(self.IsElementPresent,
                   "css=td:contains('Depth') ~ td:nth(0):contains('1')")

    # Check that flow id of this flow has forward slash - i.e. consists of
    # 2 components.
    self.WaitUntil(self.IsTextPresent, "Flow ID")
    flow_id = self.GetText("css=dt:contains('Flow ID') ~ dd:nth(0)")
    self.assertTrue("/" in flow_id)

  def testOverviewIsShownForNestedHuntFlows(self):
    with implementation.GRRHunt.StartHunt(
        hunt_name=standard.GenericHunt.__name__,
        flow_runner_args=rdf_flows.FlowRunnerArgs(
            flow_name=gui_test_lib.RecursiveTestFlow.__name__),
        client_rate=0,
        token=self.token) as hunt:
      hunt.Run()

    self.AssignTasksToClients(client_ids=[self.client_id])
    self.RunHunt(client_ids=[self.client_id])

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")

    # There should be a RecursiveTestFlow in the list. Expand nested flows.
    self.Click("css=tr:contains('RecursiveTestFlow') span.tree_branch")
    # Click on a nested flow.
    self.Click("css=tr:contains('RecursiveTestFlow'):nth(2)")

    # Nested flow should have Depth argument set to 1.
    self.WaitUntil(self.IsElementPresent,
                   "css=td:contains('Depth') ~ td:nth(0):contains('1')")

    # Check that flow id of this flow has forward slash - i.e. consists of
    # 2 components.
    self.WaitUntil(self.IsTextPresent, "Flow ID")
    flow_id = self.GetText("css=dt:contains('Flow ID') ~ dd:nth(0)")
    self.assertTrue("/" in flow_id)

  def testLogsCanBeOpenedByClickingOnLogsTab(self):
    # RecursiveTestFlow doesn't send any results back.
    for _ in test_lib.TestFlowHelper(
        gui_test_lib.FlowWithOneLogStatement.__name__,
        self.action_mock,
        client_id=self.client_id,
        token=self.token):
      pass

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('FlowWithOneLogStatement')")
    self.Click("css=li[heading=Log]")

    self.WaitUntil(self.IsTextPresent, "I do log.")

  def testLogTimestampsArePresentedInUTC(self):
    with test_lib.FakeTime(42):
      for _ in test_lib.TestFlowHelper(
          gui_test_lib.FlowWithOneLogStatement.__name__,
          self.action_mock,
          client_id=self.client_id,
          token=self.token):
        pass

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('FlowWithOneLogStatement')")
    self.Click("css=li[heading=Log]")

    self.WaitUntil(self.IsTextPresent, "1970-01-01 00:00:42 UTC")

  def testResultsAreDisplayedInResultsTab(self):
    for _ in test_lib.TestFlowHelper(
        gui_test_lib.FlowWithOneStatEntryResult.__name__,
        self.action_mock,
        client_id=self.client_id,
        token=self.token):
      pass

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('FlowWithOneStatEntryResult')")
    self.Click("css=li[heading=Results]")

    self.WaitUntil(self.IsTextPresent,
                   "aff4:/C.0000000000000001/fs/os/some/unique/path")

  def testEmptyTableIsDisplayedInResultsWhenNoResults(self):
    flow.GRRFlow.StartFlow(
        flow_name=gui_test_lib.FlowWithOneStatEntryResult.__name__,
        client_id=self.client_id,
        sync=False,
        token=self.token)

    self.Open("/#c=" + self.client_id.Basename())
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('FlowWithOneStatEntryResult')")
    self.Click("css=li[heading=Results]")

    self.WaitUntil(self.IsElementPresent, "css=#main_bottomPane table thead "
                   "th:contains('Value')")

  def testHashesAreDisplayedCorrectly(self):
    for _ in test_lib.TestFlowHelper(
        gui_test_lib.FlowWithOneHashEntryResult.__name__,
        self.action_mock,
        client_id=self.client_id,
        token=self.token):
      pass

    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('FlowWithOneHashEntryResult')")
    self.Click("css=li[heading=Results]")

    self.WaitUntil(self.IsTextPresent,
                   "9e8dc93e150021bb4752029ebbff51394aa36f069cf19901578"
                   "e4f06017acdb5")
    self.WaitUntil(self.IsTextPresent,
                   "6dd6bee591dfcb6d75eb705405302c3eab65e21a")
    self.WaitUntil(self.IsTextPresent, "8b0a15eefe63fd41f8dc9dee01c5cf9a")

  def testApiExampleIsShown(self):
    flow_urn = flow.GRRFlow.StartFlow(
        flow_name=gui_test_lib.FlowWithOneStatEntryResult.__name__,
        client_id=self.client_id,
        token=self.token)

    flow_id = flow_urn.Basename()
    self.Open("/#/clients/C.0000000000000001/flows/%s/api" % flow_id)

    self.WaitUntil(self.IsTextPresent,
                   "HTTP (authentication details are omitted)")
    self.WaitUntil(self.IsTextPresent,
                   'curl -X POST -H "Content-Type: application/json"')
    self.WaitUntil(self.IsTextPresent, '"@type": "type.googleapis.com/')
    self.WaitUntil(
        self.IsTextPresent,
        '"name": "%s"' % gui_test_lib.FlowWithOneStatEntryResult.__name__)

  def testChangingTabUpdatesUrl(self):
    flow_urn = flow.GRRFlow.StartFlow(
        flow_name=gui_test_lib.FlowWithOneStatEntryResult.__name__,
        client_id=self.client_id,
        token=self.token)

    flow_id = flow_urn.Basename()
    base_url = "/#/clients/C.0000000000000001/flows/%s" % flow_id

    self.Open(base_url)

    self.Click("css=li[heading=Requests]")
    self.WaitUntilEqual(base_url + "/requests", self.GetCurrentUrlPath)

    self.Click("css=li[heading=Results]")
    self.WaitUntilEqual(base_url + "/results", self.GetCurrentUrlPath)

    self.Click("css=li[heading=Log]")
    self.WaitUntilEqual(base_url + "/log", self.GetCurrentUrlPath)

    self.Click("css=li[heading='Flow Information']")
    self.WaitUntilEqual(base_url, self.GetCurrentUrlPath)

    self.Click("css=li[heading=API]")
    self.WaitUntilEqual(base_url + "/api", self.GetCurrentUrlPath)

  def testDirectLinksToFlowsTabsWorkCorrectly(self):
    flow_urn = flow.GRRFlow.StartFlow(
        flow_name=gui_test_lib.FlowWithOneStatEntryResult.__name__,
        client_id=self.client_id,
        token=self.token)

    flow_id = flow_urn.Basename()
    base_url = "/#/clients/C.0000000000000001/flows/%s" % flow_id

    self.Open(base_url + "/requests")
    self.WaitUntil(self.IsElementPresent, "css=li.active[heading=Requests]")

    self.Open(base_url + "/results")
    self.WaitUntil(self.IsElementPresent, "css=li.active[heading=Results]")

    self.Open(base_url + "/log")
    self.WaitUntil(self.IsElementPresent, "css=li.active[heading=Log]")

    # Check that both clients/.../flows/... and clients/.../flows/.../ URLs
    # work.
    self.Open(base_url)
    self.WaitUntil(self.IsElementPresent,
                   "css=li.active[heading='Flow Information']")

    self.Open(base_url + "/")
    self.WaitUntil(self.IsElementPresent,
                   "css=li.active[heading='Flow Information']")

  def testCancelFlowWorksCorrectly(self):
    """Tests that cancelling flows works."""
    flow.GRRFlow.StartFlow(
        client_id=self.client_id,
        flow_name=gui_test_lib.RecursiveTestFlow.__name__,
        token=self.token)

    # Open client and find the flow
    self.Open("/")

    self.Type("client_query", "C.0000000000000001")
    self.Click("client_query_submit")

    self.WaitUntilEqual(u"C.0000000000000001", self.GetText,
                        "css=span[type=subject]")
    self.Click("css=td:contains('0001')")
    self.Click("css=a[grrtarget='client.flows']")

    self.Click("css=td:contains('RecursiveTestFlow')")
    self.Click("css=button[name=cancel_flow]")

    # The window should be updated now
    self.WaitUntil(self.IsTextPresent, "Cancelled in GUI")


def main(argv):
  # Run the full test suite
  runtests_test.SeleniumTestProgram(argv=argv)


if __name__ == "__main__":
  flags.StartMain(main)
