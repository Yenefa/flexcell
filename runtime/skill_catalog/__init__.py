"""Read-only robot-action skill catalog (issue #245).

This package returns DECLARATIONS only. It does not dispatch actions, judge
physical feasibility, load ROS, or change any controller or acceptance rule.
"""

from .core import (CatalogError, SkillNotFound, get_skill, list_skills,
                   load_catalog)

__all__ = ["CatalogError", "SkillNotFound", "get_skill", "list_skills",
           "load_catalog"]
