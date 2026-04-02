from src.skills.base import BaseSkill, SkillMetadata, SkillResult


class GraphQuerySkill(BaseSkill[dict]):
    """Skill for querying the knowledge graph"""

    def __init__(self):
        super().__init__(
            SkillMetadata(
                name="graph_query",
                description="Queries knowledge graph for context",
                tools_required=["graph_store"],
                context_needed=["target_entities"],
            )
        )

    async def execute(self, input_data: dict) -> SkillResult:
        """Query graph for information"""
        query_type = input_data.get("type", "node")
        graph_tool = self._tools.get("graph_store")

        if not graph_tool:
            return SkillResult(success=False, error="Graph store tool not available")

        try:
            if query_type == "node":
                return await self._query_node(input_data, graph_tool)
            elif query_type == "related":
                return await self._query_related(input_data, graph_tool)
            elif query_type == "by_type":
                return await self._query_by_type(input_data, graph_tool)
            elif query_type == "stats":
                return await self._query_stats(input_data, graph_tool)
            else:
                return SkillResult(
                    success=False, error=f"Unknown query type: {query_type}"
                )
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _query_node(self, input_data: dict, graph_tool) -> SkillResult:
        """Query a specific node by ID"""
        node_id = input_data.get("node_id")
        if not node_id:
            return SkillResult(success=False, error="node_id required")

        result = await graph_tool.execute(operation="get_node", node_id=node_id)

        if result.success:
            return SkillResult(
                success=True,
                output={"type": "node", "node": result.output},
                metadata={"skill": "graph_query", "query_type": "node"},
            )
        return SkillResult(success=False, error=result.error)

    async def _query_related(self, input_data: dict, graph_tool) -> SkillResult:
        """Query nodes related to a given node"""
        node_id = input_data.get("node_id")
        if not node_id:
            return SkillResult(success=False, error="node_id required")

        result = await graph_tool.execute(operation="get_out_edges", node_id=node_id)

        if result.success:
            return SkillResult(
                success=True,
                output={"type": "related", "edges": result.output},
                metadata={"skill": "graph_query", "query_type": "related"},
            )
        return SkillResult(success=False, error=result.error)

    async def _query_by_type(self, input_data: dict, graph_tool) -> SkillResult:
        """Query all nodes of a specific type"""
        node_type = input_data.get("node_type")
        if not node_type:
            return SkillResult(success=False, error="node_type required")

        result = await graph_tool.execute(operation="query_nodes", node_type=node_type)

        if result.success:
            return SkillResult(
                success=True,
                output={
                    "type": "by_type",
                    "node_type": node_type,
                    "nodes": result.output,
                },
                metadata={"skill": "graph_query", "query_type": "by_type"},
            )
        return SkillResult(success=False, error=result.error)

    async def _query_stats(self, input_data: dict, graph_tool) -> SkillResult:
        """Query graph statistics"""
        node_result = await graph_tool.execute(operation="node_count")
        edge_result = await graph_tool.execute(operation="edge_count")

        if node_result.success and edge_result.success:
            return SkillResult(
                success=True,
                output={
                    "type": "stats",
                    "node_count": node_result.output,
                    "edge_count": edge_result.output,
                },
                metadata={"skill": "graph_query", "query_type": "stats"},
            )
        return SkillResult(success=False, error="Failed to get graph stats")
