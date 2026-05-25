"""email-multi plugin: Multi-account IMAP/SMTP email adapter."""

from pathlib import Path

from . import schemas, tools

PLUGIN_DIR = Path(__file__).resolve().parent


def register(ctx):
    """Register plugin tools and bundled skill with Hermes context."""
    for schema in schemas.TOOLS:
        tool_name = schema["name"]
        handler = getattr(tools, tool_name)
        ctx.register_tool(
            name=tool_name,
            toolset="email_multi",
            schema=schema,
            handler=handler,
        )

    skill_md = PLUGIN_DIR / "skill" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("email-multi", skill_md, "Multi-account IMAP/SMTP email workflow")
