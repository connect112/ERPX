"""
Pentrix module — top-level router aggregator.

Mounted at /pentrix. Labs, Challenges, Leaderboard, Achievements, and
Certifications get their own sub-prefixes; Lab Instances, Flags, and
Hints share the root since they already embed their full nested path.
"""

from fastapi import APIRouter

from modules.pentrix.achievements.routes import router as achievements_router
from modules.pentrix.certifications.routes import router as certifications_router
from modules.pentrix.challenges.routes import router as challenges_router
from modules.pentrix.flags.routes import router as flags_router
from modules.pentrix.hints.routes import router as hints_router
from modules.pentrix.lab_instances.routes import router as lab_instances_router
from modules.pentrix.labs.routes import router as labs_router
from modules.pentrix.leaderboard.routes import router as leaderboard_router

router = APIRouter()

router.include_router(labs_router, prefix="/labs", tags=["Pentrix - Labs"])
router.include_router(challenges_router, prefix="/challenges", tags=["Pentrix - Challenges"])
router.include_router(leaderboard_router, prefix="/leaderboard", tags=["Pentrix - Leaderboard"])
router.include_router(achievements_router, prefix="/achievements", tags=["Pentrix - Achievements"])
router.include_router(
    certifications_router, prefix="/certifications", tags=["Pentrix - Certifications"]
)
router.include_router(lab_instances_router, tags=["Pentrix - Lab Instances"])
router.include_router(flags_router, tags=["Pentrix - Flags"])
router.include_router(hints_router, tags=["Pentrix - Hints"])
