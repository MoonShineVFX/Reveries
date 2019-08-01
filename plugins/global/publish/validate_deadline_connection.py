
import os
import subprocess
import pyblish.api
import avalon.api as api
from avalon.vendor import requests
from reveries.plugins import context_process


class ValidateDeadlineConnection(pyblish.api.InstancePlugin):
    """Validate Deadline Web Service is running"""

    label = "Deadline Connection"
    order = pyblish.api.ValidatorOrder + 0.1
    families = [
        "reveries.pointcache",
        "reveries.imgseq",
    ]

    @context_process
    def process(self, context):

        if not any(i.data.get("deadlineEnable") for i in context):
            self.log.debug("No instance require deadline.")
            return

        AVALON_DEADLINE = api.Session.get("AVALON_DEADLINE")

        if AVALON_DEADLINE:

            # Testing Deadline web-service
            self.log.info("Testing Deadline Web Service: {}"
                          "".format(AVALON_DEADLINE))

            # Check response
            response = requests.get(AVALON_DEADLINE)

            if (response.ok and
                    response.text.startswith("Deadline Web Service ")):
                self.log.info("Deadline Web Service on-line.")

                return

            else:
                self.log.warning("Web service did not respond.")
        else:
            self.log.warning("No available Deadline Web Service.")

        # Plan B

        AVALON_DEADLINE_APP = api.Session.get("AVALON_DEADLINE_APP")

        if AVALON_DEADLINE_APP:

            # Testing Deadline command application
            self.log.info("Testing Deadline Command App: {}"
                          "".format(AVALON_DEADLINE_APP))

            if not os.path.isfile(AVALON_DEADLINE_APP):
                raise Exception("Deadline Command App not exists.")

            test_cmd = AVALON_DEADLINE_APP + " GetRepositoryVersion"
            output = subprocess.check_output(test_cmd)

            if output.startswith(b"Repository Version:"):
                output = output.decode("utf-8")
                self.log.info("Deadline Command App on-line, repository "
                              "version: {}".format(output.split("\n")[0]))

                context.data["USE_DEADLINE_APP"] = True
                return

        else:
            self.log.warning("No available Deadline Command App.")

        # Got non
        raise Exception("No available Deadline connection.")
