#!/usr/bin/env python
"""Test hunt creation by flow."""


from grr.gui import gui_test_lib
from grr.gui import runtests_test

from grr.lib import action_mocks
from grr.lib import aff4
from grr.lib import flags
from grr.lib import flow
from grr.lib import output_plugin
from grr.lib.flows.general import processes as flows_processes
from grr.lib.hunts import standard_test
from grr.lib.output_plugins import email_plugin
from grr.lib.rdfvalues import client as rdf_client


class TestFlowCreateHunt(gui_test_lib.GRRSeleniumTest,
                         standard_test.StandardHuntTestMixin):

  def setUp(self):
    super(TestFlowCreateHunt, self).setUp()
    self.client_id = rdf_client.ClientURN("C.0000000000000001")
    with aff4.FACTORY.Open(
        self.client_id, mode="rw", token=self.token) as client:
      client.Set(client.Schema.HOSTNAME("HostC.0000000000000001"))
    self.RequestAndGrantClientApproval(self.client_id)
    self.action_mock = action_mocks.FileFinderClientMock()

  def testCreateHuntFromFlow(self):
    email_descriptor = output_plugin.OutputPluginDescriptor(
        plugin_name=email_plugin.EmailOutputPlugin.__name__,
        plugin_args=email_plugin.EmailOutputPluginArgs(
            email_address="test@localhost", emails_limit=42))

    args = flows_processes.ListProcessesArgs(
        filename_regex="test[a-z]*", fetch_binaries=True)

    flow.GRRFlow.StartFlow(
        flow_name=flows_processes.ListProcesses.__name__,
        args=args,
        client_id=self.client_id,
        output_plugins=[email_descriptor],
        token=self.token)

    # Navigate to client and select newly created flow.
    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")
    self.Click("css=td:contains('ListProcesses')")

    # Open wizard and check if flow arguments are copied.
    self.Click("css=button[name=create_hunt]")

    self.WaitUntilEqual("test[a-z]*", self.GetValue,
                        "css=label:contains('Filename Regex') ~ * input")

    self.WaitUntil(self.IsChecked, "css=label:contains('Fetch Binaries') "
                   "~ * input[type=checkbox]")

    # Go to next page and check that we did not copy the output plugins.
    self.Click("css=button:contains('Next')")

    self.WaitUntilNot(self.IsElementPresent,
                      "css=grr-output-plugin-descriptor-form")

    # Nothing else to check, so finish the hunt.
    self.Click("css=button:contains('Next')")
    self.Click("css=button:contains('Next')")
    self.Click("css=button:contains('Create Hunt')")
    self.Click("css=button:contains('Done')")

    # Check that we get redirected to ManageHunts.
    self.WaitUntilEqual(1, self.GetCssCount,
                        "css=grr-hunts-list table tbody tr")
    self.WaitUntilEqual(1, self.GetCssCount,
                        "css=grr-hunts-list table tbody tr.row-selected")
    self.WaitUntil(self.IsTextPresent, "GenericHunt")
    self.WaitUntil(self.IsTextPresent, flows_processes.ListProcesses.__name__)

  def testCheckCreateHuntButtonIsOnlyEnabledWithFlowSelection(self):
    flow.GRRFlow.StartFlow(
        client_id=self.client_id,
        flow_name=gui_test_lib.RecursiveTestFlow.__name__,
        token=self.token)

    # Open client and find the flow.
    self.Open("/#c=C.0000000000000001")
    self.Click("css=a[grrtarget='client.flows']")

    # No flow selected, so the button should be disabled.
    self.WaitUntil(self.IsElementPresent,
                   "css=button[name=create_hunt][disabled]")

    # And enabled after selecting the test flow.
    self.Click("css=td:contains('RecursiveTestFlow')")
    self.WaitUntil(self.IsElementPresent,
                   "css=button[name=create_hunt]:not([disabled])")


def main(argv):
  # Run the full test suite
  runtests_test.SeleniumTestProgram(argv=argv)


if __name__ == "__main__":
  flags.StartMain(main)
