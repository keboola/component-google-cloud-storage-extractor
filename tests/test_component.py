'''
Created on 12. 11. 2018

@author: esner
'''
import json
import shutil
import tempfile
import unittest
import mock
import os
from freezegun import freeze_time

from component import Component, UserException


class TestComponent(unittest.TestCase):

    # set global time to 2010-10-10 - affects functions like datetime.now()
    @freeze_time("2010-10-10")
    # set KBC_DATADIR env to non-existing dir
    @mock.patch.dict(os.environ, {'KBC_DATADIR': './non-existing-dir'})
    def test_run_no_cfg_fails(self):
        with self.assertRaises(ValueError):
            comp = Component()
            comp.run()


class TestConfigurationParsing(unittest.TestCase):
    """The configuration is parsed before anything is downloaded, so these tests need no Google Cloud access."""

    def _build_data_dir(self, parameters: dict) -> str:
        data_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, data_dir, True)
        with open(os.path.join(data_dir, "config.json"), "w") as config_file:
            json.dump({"parameters": parameters}, config_file)
        return data_dir

    def test_valid_file_names_array_is_parsed(self):
        """Happy path: a valid configuration is still parsed exactly as before."""
        data_dir = self._build_data_dir({
            "#service_account_key": "{}",
            "files": {"bucket_name": "dummy-bucket", "file_names_array": ["dummy.csv"]}
        })

        with mock.patch.dict(os.environ, {'KBC_DATADIR': data_dir}):
            comp = Component()
            comp._init_configuration()

        self.assertEqual(["dummy.csv"], comp._configuration.files.file_names_array)
        self.assertEqual("dummy-bucket", comp._configuration.files.bucket_name)

    def test_null_entry_in_file_names_array_raises_user_exception(self):
        """A null entry in the file names list must fail as a user error, not as an internal error."""
        data_dir = self._build_data_dir({
            "#service_account_key": "{}",
            "files": {"bucket_name": "dummy-bucket", "file_names_array": [None]}
        })

        with mock.patch.dict(os.environ, {'KBC_DATADIR': data_dir}):
            comp = Component()
            with self.assertRaises(UserException) as raised:
                comp.run()

        message = str(raised.exception)
        self.assertIn("configuration is invalid", message)
        self.assertIn("file_names_array", message)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
