import unittest

from apps.entities.plugin import *


class TestToolData(unittest.TestCase):
    def test_valid_tool_data(self):
        data = {
            "name": "sql",
            "params": {
                "test_key": "test_value"
            }
        }

        tool_data = ToolData.model_validate(data)
        self.assertEqual(tool_data.model_dump(), tool_data)

    def test_invalid_tool_data(self):
        data = {
            "name": "sql",
        }
        self.assertRaises(Exception, ToolData.model_validate, data)


class TestStep(unittest.TestCase):
    def test_valid_step(self):
        data = {
            "name": "test_api",
            "call_type": "api",
            "params": {
                "test_key": "test_value"
            },
            "next": "test_next"
        }

        step = Step.model_validate(data)
        self.assertEqual(step.model_dump(), step)

    def test_invalid_step(self):
        data = {

        }

