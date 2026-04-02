from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.graph.graph import HeterogeneousGraph

from src.tools.base import BaseTool, ToolResult


class GraphStoreTool(BaseTool):
    name = "graph_store"
    description = "Query and update the knowledge graph"

    def __init__(self, graph: "HeterogeneousGraph"):
        self.graph = graph

    async def execute(self, operation: str, **kwargs) -> ToolResult:
        try:
            if operation == "query_nodes":
                node_type = kwargs.get("node_type")
                if node_type:
                    nodes = self.graph.get_nodes_by_type(node_type)
                    return ToolResult(
                        success=True, output=[n.model_dump() for n in nodes]
                    )
                return ToolResult(success=False, error="node_type required")

            elif operation == "get_node":
                node_id = kwargs.get("node_id")
                if node_id:
                    node = self.graph.get_node(node_id)
                    if node:
                        return ToolResult(success=True, output=node.model_dump())
                    return ToolResult(success=False, error=f"Node not found: {node_id}")
                return ToolResult(success=False, error="node_id required")

            elif operation == "has_node":
                node_id = kwargs.get("node_id")
                if node_id:
                    return ToolResult(success=True, output=self.graph.has_node(node_id))
                return ToolResult(success=False, error="node_id required")

            elif operation == "get_out_edges":
                node_id = kwargs.get("node_id")
                if node_id:
                    edges = self.graph.get_out_edges(node_id)
                    return ToolResult(
                        success=True,
                        output=[
                            {"target": t, "relation": r, "weight": w}
                            for t, r, w in edges
                        ],
                    )
                return ToolResult(success=False, error="node_id required")

            elif operation == "node_count":
                return ToolResult(success=True, output=self.graph.node_count())

            elif operation == "edge_count":
                return ToolResult(success=True, output=self.graph.edge_count())

            else:
                return ToolResult(
                    success=False, error=f"Unknown operation: {operation}"
                )

        except Exception as e:
            return ToolResult(success=False, error=str(e))
