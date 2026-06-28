import ast
import io
import os
import time
import platform
import textwrap
import traceback
from contextlib import redirect_stdout
from datetime import datetime, timedelta

import discord
from discord.ext import commands

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


class UtilityCore(commands.Cog):
    """Core utility commands (ping, info, uptime)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _cleanup_code(self, content: str) -> str:
        if content.startswith("```") and content.endswith("```"):
            content = "\n".join(content.splitlines()[1:-1])
        return content.strip("` \n")

    def _format_duration(self, duration: timedelta) -> str:
        total_seconds = int(duration.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def _get_system_uptime(self) -> timedelta | None:
        if PSUTIL_AVAILABLE:
            return timedelta(seconds=(time.time() - psutil.boot_time()))
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                uptime_seconds = float(f.readline().split()[0])
            return timedelta(seconds=uptime_seconds)
        except Exception:
            return None

    def _get_process_info(self) -> dict[str, str]:
        info: dict[str, str] = {}
        pid = os.getpid()
        info["pid"] = str(pid)
        if PSUTIL_AVAILABLE:
            proc = psutil.Process(pid)
            mem = proc.memory_info()
            info["memory_rss"] = f"{mem.rss / 1024**2:.2f} MB"
            info["memory_vms"] = f"{mem.vms / 1024**2:.2f} MB"
            info["cpu_percent"] = f"{proc.cpu_percent(interval=0.1):.1f}%"
            info["threads"] = str(proc.num_threads())
            info["process_uptime"] = self._format_duration(
                timedelta(seconds=(time.time() - proc.create_time()))
            )
        else:
            info["process_uptime"] = self._format_duration(
                timedelta(seconds=(time.time() - os.path.getmtime(f"/proc/{pid}/cmdline")))
            ) if os.path.exists(f"/proc/{pid}/cmdline") else "Unknown"
        return info

    def _format_code_result(self, result: object) -> str:
        text = repr(result)
        if len(text) > 1900:
            return text[:1900] + "..."
        return text

    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        start = time.perf_counter()
        message = await ctx.send("Pinging...")
        elapsed = (time.perf_counter() - start) * 1000
        await message.edit(
            content=f"Pong! 🏓\nGateway: `{self.bot.latency * 1000:.1f}ms`\nRoundtrip: `{elapsed:.1f}ms`"
        )

    @commands.hybrid_command(
        name="info", description="Shows information about the bot."
    )
    async def info(self, ctx: commands.Context):
        await ctx.send(
            f"🤖 Bot Info\n{self.bot.user.display_avatar.url}\n- Name: {self.bot.user.name}\n- ID: {self.bot.user.id}\n- Servers: {len(self.bot.guilds)}\n- Python: {platform.python_version()}\n- Discord.py: {discord.__version__}\n- Created At: {discord.utils.format_dt(self.bot.user.created_at, 'R')}"
        )

    @commands.hybrid_command(
        name="uptime",
        description="Check how long the bot has been online and view system/process metrics.",
        help="Shows bot uptime, process details, and system metrics for a professional status report.",
    )
    async def uptime(self, ctx: commands.Context):
        bot_delta = discord.utils.utcnow() - self.bot.start_time
        bot_uptime = self._format_duration(bot_delta)
        system_uptime = self._get_system_uptime()
        process_info = self._get_process_info()

        cpu_info = "Unknown"
        mem_info = "Unknown"
        if PSUTIL_AVAILABLE:
            cpu_info = f"{psutil.cpu_percent(interval=0.1):.1f}%"
            vm = psutil.virtual_memory()
            mem_info = f"{vm.used / 1024**2:.2f}/{vm.total / 1024**2:.2f} MB ({vm.percent:.1f}%)"
        elif hasattr(os, "getloadavg"):
            load1, load5, load15 = os.getloadavg()
            cpu_info = f"loadavg {load1:.2f}, {load5:.2f}, {load15:.2f}"

        embed = discord.Embed(
            title="Bot Uptime & Health",
            color=discord.Color.blurple(),
            description="Professional uptime details for this bot instance.",
        )
        embed.add_field(name="Bot Uptime", value=bot_uptime, inline=False)
        embed.add_field(
            name="Process Uptime",
            value=process_info.get("process_uptime", "Unknown"),
            inline=False,
        )
        embed.add_field(
            name="System Uptime",
            value=self._format_duration(system_uptime) if system_uptime else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Gateway & Activity",
            value=(
                f"Guilds: {len(self.bot.guilds)}\n"
                f"Latency: {self.bot.latency * 1000:.1f}ms\n"
                f"CPU: {cpu_info}\n"
                f"System RAM: {mem_info}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Process Details",
            value=(
                f"PID: {process_info.get('pid')}\n"
                f"RSS: {process_info.get('memory_rss', 'Unknown')}\n"
                f"VMS: {process_info.get('memory_vms', 'Unknown')}\n"
                f"CPU%: {process_info.get('cpu_percent', 'Unknown')}\n"
                f"Threads: {process_info.get('threads', 'Unknown')}"
            ),
            inline=False,
        )
        if self.bot.shard_count:
            embed.add_field(name="Shard Count", value=str(self.bot.shard_count), inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="eval",
        description="Evaluate Python code as the bot owner.",
        help="Run Python code directly from Discord for quick testing and debugging.",
    )
    @commands.is_owner()
    async def eval_code(self, ctx: commands.Context, *, code: str):
        await ctx.defer()
        source = self._cleanup_code(code)
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "discord": discord,
            "asyncio": __import__("asyncio"),
            "os": os,
            "time": time,
            "platform": platform,
            "psutil": psutil,
            "db": getattr(self.bot, "db", None),
            "__name__": "__main__",
        }
        env.update(globals())

        try:
            parsed = ast.parse(source, mode="exec")
            if parsed.body and isinstance(parsed.body[-1], ast.Expr):
                parsed.body[-1] = ast.Return(parsed.body[-1].value)
            compiled = compile(parsed, filename="<eval>", mode="exec")
        except SyntaxError as exc:
            await ctx.send(
                f"❌ Syntax Error:\n```py\n{exc.text or ''}{exc.__class__.__name__}: {exc}\n```")
            return

        func_code = "async def __evaluate():\n" + textwrap.indent(source, "    ")
        try:
            exec(compiled, env)
            function = env.get("__evaluate")
            if function is None:
                exec(func_code, env)
                function = env["__evaluate"]

            stdout_buffer = io.StringIO()
            with redirect_stdout(stdout_buffer):
                result = await function()
            stdout_value = stdout_buffer.getvalue().strip()

            response = []
            if stdout_value:
                response.append(f"📤 Output:\n```py\n{stdout_value}\n```")
            if result is not None:
                response.append(f"✅ Result:\n```py\n{self._format_code_result(result)}\n```")
            if not response:
                response.append("✅ Evaluation completed successfully. No output.")

            await ctx.send("\n".join(response))
        except Exception:
            await ctx.send(
                f"❌ Error:\n```py\n{traceback.format_exc()[:1900]}\n```")


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCore(bot))
