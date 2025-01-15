import unittest
from apps.scheduler.call import CallRegistry


class TestSqlTool(unittest.TestCase):

    def test_tool(self):
        tool = CallRegistry.get('sql')(context=None, question="数学课的老师多少岁", agent_params=None)
        result = tool(params=None)
        print(result)
        self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
