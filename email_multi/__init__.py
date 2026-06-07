"""email-multi plugin: Multi-account IMAP/SMTP email adapter."""

from pathlib import Path

from . import auth as auth
from . import config as config
from . import schemas, tools
from . import service as service

PLUGIN_DIR = Path(__file__).resolve().parent


def register(ctx):
    """Register plugin tools and bundled skill with Hermes context.

    Args:
        ctx: Hermes plugin context with register_tool() and register_skill().
    """
    # Register all tool handlers
    for schema in schemas.TOOLS:
        tool_name = schema["name"]
        handler = getattr(tools, tool_name)
        ctx.register_tool(
            name=tool_name,
            toolset="email_multi",
            schema=schema,
            handler=handler,
        )

    # Register bundled skill documentation
    skill_md = PLUGIN_DIR / "skill" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("email-multi", skill_md)
