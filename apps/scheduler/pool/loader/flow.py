class FlowLoader:
    """工作流加载器"""

    @staticmethod
    async def generate(flow_id: str) -> None:
        """从数据库中加载工作流"""
        pass


    @staticmethod
    def load() -> None:
        """执行工作流加载"""
        pass



def _load_flow(self) -> list[dict[str, Any]]:
        flow_path = self._plugin_location / FLOW_DIR
        flows = []
        if flow_path.is_dir():
            for current_flow_path in flow_path.iterdir():
                LOGGER.info(f"载入Flow： {current_flow_path}")

                with Path(current_flow_path).open(encoding="utf-8") as f:
                    flow_yaml = yaml.safe_load(f)

                if "/" in flow_yaml["id"]:
                    err = "Flow名称包含非法字符！"
                    raise ValueError(err)

                if "on_error" in flow_yaml:
                    error_step = Step(name="error", **flow_yaml["on_error"])
                else:
                    error_step = Step(
                        name="error",
                        call_type="llm",
                        params={
                            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}",
                        },
                    )

                steps = {}
                for step in flow_yaml["steps"]:
                    steps[step["name"]] = Step(**step)

                if "next_flow" not in flow_yaml:
                    next_flow = None
                else:
                    next_flow = []
                    for next_flow_item in flow_yaml["next_flow"]:
                        next_flow.append(NextFlow(
                            id=next_flow_item["id"],
                            question=next_flow_item["question"],
                        ))
                flows.append({
                    "id": flow_yaml["id"],
                    "description": flow_yaml["description"],
                    "data": Flow(on_error=error_step, steps=steps, next_flow=next_flow),
                })
        return flows