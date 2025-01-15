import unittest
from apps.scheduler.call import tools


class TestSqlTool(unittest.TestCase):

    def test_tool_bar(self):
        tool = tools['render'](context=None, question="柱状图", agent_params={"data":[{"count":100,"name":"小明"},{"count":200,"name":"小红"}],"session_id":"111"})
        result = tool(params=None)
        print(result)
        self.assertIsInstance(result, dict)

    def test_tool_pie(self):
        tool = tools['render'](context=None, question="饼图", agent_params={"data":[{"count":100,"name":"小明"},{"count":200,"name":"小红"}],"session_id":"111"})
        result = tool(params=None)
        print(result)
        self.assertIsInstance(result, dict)

    def test_tool_line(self):
        tool = tools['render'](context=None, question="折线图", agent_params={"data":[{"count":100,"name":"小明"},{"count":200,"name":"小红"}],"session_id":"111"})
        result = tool(params=None)
        print(result)
        self.assertIsInstance(result, dict)

    def test_tool_scatter(self):
        tool = tools['render'](context=None, question="散点图", agent_params={"data":[{"count":100,"name":"小明"},{"count":200,"name":"小红"}],"session_id":"111"})
        result = tool(params=None)
        print(result)
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()
