# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk
from sgtk import TankError
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation

class TestLauncher(SoftwareLauncher):
    """
    SoftwareLauncher stub for unit testing.
    """
    def scan_software(self, versions=None, display_name=None, icon=None):
        """
        Performs a scan for software installations.

        :param list versions: List of strings representing versions
                              to search for. If set to None, search
                              for all versions. A version string is
                              DCC-specific but could be something
                              like "2017", "6.3v7" or "1.2.3.52".
        :param str display_name : (optional) Name to use in graphical
                                  displays to describe the
                                  SoftwareVersions that were found.
        :param icon: (optional) Path to a 256x256 (or smaller) png file
                     to use in graphical displays for every SoftwareVersion
                     found.
        :returns: List of :class:`SoftwareVersion` instances
        """
        sw_versions = []
        for version in versions or []:
            sw_path = "/path/to/unit/test/app/%s/executable"
            sw_icon = "%s/icons/exec.png" % os.path.dirname(sw_path)
            sw_versions.append(SoftwareVersion(
                version, (display_name or "Unit Test App"),
                sw_path, (icon or sw_icon),
            ))
        return sw_versions

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares the given software for launch.

        :param str exec_path: Path to DCC executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on launch.
        :returns: :class:`LaunchInformation` instance
        """
        required_env = {}
        startup_path = os.path.join(self.disk_location, "startup")
        sgtk.util.append_path_to_env_var("PYTHONPATH", startup_path)
        required_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        if file_to_open:
            required_env["FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)