class ConversationWorkflow:
    def __init__(self):
        self.graph = self.build_graph()

    def build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None
        graph = StateGraph(dict)
        graph.add_node("collecting", lambda state: state)
        graph.add_node("ready_for_confirmation", lambda state: state)
        graph.set_entry_point("collecting")
        graph.add_conditional_edges(
            "collecting",
            lambda state: "missing" if state.get("missing_fields") else "ready",
            {"missing": END, "ready": "ready_for_confirmation"},
        )
        graph.add_edge("ready_for_confirmation", END)
        return graph.compile()

    def next_state(self, missing_fields):
        if not self.graph:
            return "collecting" if missing_fields else "ready_for_confirmation"
        result = self.graph.invoke({"missing_fields": missing_fields})
        return "collecting" if result.get("missing_fields") else "ready_for_confirmation"
