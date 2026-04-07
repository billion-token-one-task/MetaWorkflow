from meta_controller.workers.base import RoleWorker


class ResearchPlannerWorker(RoleWorker):
    role = "research_planner"
    objective = "decompose the research task into evidence, hypothesis, experiment, and review stages"
    output_fields = ["research_plan", "search_axes", "deliverable_map"]
