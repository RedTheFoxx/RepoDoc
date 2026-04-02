from src.skills.base import BaseSkill


class SkillRegistry:
    _skills: dict[str, type[BaseSkill]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, name: str, skill_class: type[BaseSkill]) -> None:
        cls._skills[name] = skill_class

    @classmethod
    def get(cls, name: str) -> type[BaseSkill] | None:
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> list[str]:
        if not cls._initialized:
            cls._initialize()
        return list(cls._skills.keys())

    @classmethod
    def _initialize(cls) -> None:
        if cls._initialized:
            return
        from src.skills.code_analysis import CodeAnalysisSkill
        from src.skills.doc_writer import DocWriterSkill
        from src.skills.graph_query import GraphQuerySkill

        cls.register("code_analysis", CodeAnalysisSkill)
        cls.register("doc_writer", DocWriterSkill)
        cls.register("graph_query", GraphQuerySkill)
        cls._initialized = True


