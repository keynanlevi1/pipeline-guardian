"""CLI interface for Pipelines Guardian."""

import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Settings
from .client import JenkinsMCPClient
from .debugger import PipelineDebugger

console = Console()


def async_command(f):
    """Decorator to run async commands."""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.option("--jenkins-url", envvar="JENKINS_URL", help="Jenkins server URL")
@click.option("--jenkins-user", envvar="JENKINS_USER", help="Jenkins username")
@click.option("--jenkins-token", envvar="JENKINS_TOKEN", help="Jenkins API token")
@click.pass_context
def cli(ctx, jenkins_url, jenkins_user, jenkins_token):
    """Pipelines Guardian - AI-assisted pipeline debugging using Jenkins MCP Plugin."""
    ctx.ensure_object(dict)

    # Build settings from CLI args and env
    settings_kwargs = {}
    if jenkins_url:
        settings_kwargs["jenkins_url"] = jenkins_url
    if jenkins_user:
        settings_kwargs["jenkins_user"] = jenkins_user
    if jenkins_token:
        settings_kwargs["jenkins_token"] = jenkins_token

    ctx.obj["settings"] = Settings(**settings_kwargs)


@cli.command()
@click.pass_context
@async_command
async def tools(ctx):
    """List available MCP tools from Jenkins."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching tools from Jenkins MCP...", total=None)
        tool_list = await client.list_tools()

    table = Table(title="Jenkins MCP Tools")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Description", style="green")

    for tool in tool_list:
        table.add_row(tool.name, tool.description[:80] + "..." if len(tool.description) > 80 else tool.description)

    console.print(table)


@cli.command()
@click.pass_context
@async_command
async def running(ctx):
    """Show currently running pipelines."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching running pipelines...", total=None)
        result = await client.get_running_pipelines()

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    pipelines = result.content
    if not pipelines:
        console.print("[yellow]No pipelines currently running.[/yellow]")
        return

    table = Table(title="Running Pipelines")
    table.add_column("Job", style="cyan")
    table.add_column("Build #", style="magenta")
    table.add_column("Node", style="green")
    table.add_column("URL", style="blue")

    for p in pipelines:
        table.add_row(
            p.get("job_name", "N/A"),
            str(p.get("build_number", "N/A")),
            p.get("node", "N/A"),
            p.get("url", "N/A"),
        )

    console.print(table)


@cli.command()
@click.pass_context
@async_command
async def queue(ctx):
    """Show Jenkins build queue."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching build queue...", total=None)
        result = await client.get_queue()

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    queue_items = result.content
    if not queue_items:
        console.print("[green]Build queue is empty.[/green]")
        return

    table = Table(title="Build Queue")
    table.add_column("Job", style="cyan")
    table.add_column("Reason", style="yellow")
    table.add_column("Blocked", style="red")

    for item in queue_items:
        table.add_row(
            item.get("job_name", "N/A"),
            item.get("reason", "N/A")[:60],
            "Yes" if item.get("blocked") else "No",
        )

    console.print(table)


@cli.command()
@click.option("--date", default="today", help="Date: 'today', 'yesterday', or YYYY-MM-DD")
@click.pass_context
@async_command
async def failures(ctx, date):
    """Show failed builds for a date."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Fetching failed builds for {date}...", total=None)
        result = await client.get_failed_builds(date)

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    failures_list = result.content
    if not failures_list:
        console.print(f"[green]No failed builds for {date}.[/green]")
        return

    table = Table(title=f"Failed Builds ({date})")
    table.add_column("Job", style="cyan")
    table.add_column("Build #", style="magenta")
    table.add_column("URL", style="blue")

    for f in failures_list:
        table.add_row(
            f.get("job_name", "N/A"),
            str(f.get("build_number", "N/A")),
            f.get("url", "N/A"),
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(failures_list)} failed builds")


@cli.command()
@click.pass_context
@async_command
async def nodes(ctx):
    """Show Jenkins nodes/agents status."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching nodes...", total=None)
        result = await client.get_nodes()

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    nodes_list = result.content

    table = Table(title="Jenkins Nodes")
    table.add_column("Node", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Executors", style="magenta")
    table.add_column("Idle", style="yellow")

    for node in nodes_list:
        status = "[red]Offline[/red]" if node.get("offline") else "[green]Online[/green]"
        table.add_row(
            node.get("name", "N/A"),
            status,
            str(node.get("num_executors", 0)),
            "Yes" if node.get("idle") else "No",
        )

    console.print(table)


@cli.command()
@click.argument("job_name")
@click.option("--build", "-b", type=int, help="Build number (default: last failed)")
@click.pass_context
@async_command
async def debug(ctx, job_name, build):
    """AI-assisted debugging for a pipeline failure."""
    settings = ctx.obj["settings"]
    debugger = PipelineDebugger(settings=settings)

    console.print(f"\n[bold cyan]Analyzing failure for:[/bold cyan] {job_name}")
    if build:
        console.print(f"[bold cyan]Build:[/bold cyan] #{build}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching build information...", total=None)

        try:
            progress.update(task, description="Analyzing with AI...")
            analysis = await debugger.analyze_failure(job_name, build)
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            return

    # Display analysis results
    console.print("\n")
    console.print(Panel(
        f"[bold]{analysis.error_summary}[/bold]",
        title=f"[red]Pipeline Failure[/red] - {job_name} #{analysis.build_number}",
        border_style="red",
    ))

    console.print("\n[bold yellow]Root Cause:[/bold yellow]")
    console.print(analysis.root_cause)

    console.print("\n[bold green]Suggested Fixes:[/bold green]")
    for i, fix in enumerate(analysis.suggested_fixes, 1):
        console.print(f"  {i}. {fix}")

    if analysis.related_files:
        console.print("\n[bold blue]Related Files:[/bold blue]")
        for f in analysis.related_files:
            console.print(f"  - {f}")

    confidence_color = "green" if analysis.confidence > 0.7 else "yellow" if analysis.confidence > 0.4 else "red"
    console.print(f"\n[bold]Confidence:[/bold] [{confidence_color}]{analysis.confidence:.0%}[/{confidence_color}]")


@cli.command()
@click.argument("job_name")
@click.option("--build", "-b", type=int, help="Build number (default: last)")
@click.option("--lines", "-n", default=100, help="Number of lines to show")
@click.pass_context
@async_command
async def logs(ctx, job_name, build, lines):
    """Show console output for a build."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    if not build:
        job_result = await client.get_job_details(job_name)
        if job_result.success:
            last_build = job_result.content.get("last_build", {})
            build = last_build.get("number", 1)
        else:
            console.print(f"[red]Error getting job details:[/red] {job_result.error}")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching console output...", total=None)
        result = await client.get_build_console(job_name, build, lines)

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    content = result.content
    if isinstance(content, dict):
        console.print(f"[bold]Build:[/bold] {content.get('job_name', job_name)} #{content.get('build_number', build)}")
        console.print(f"[bold]Result:[/bold] {content.get('result', 'N/A')}")

        if content.get("failure_reason"):
            console.print(f"\n[red bold]Failure Reason:[/red bold] {content['failure_reason']}")

        console.print("\n[bold]Console Output:[/bold]")
        console.print(content.get("console_tail", "No output"))
    else:
        console.print(content)


@cli.command()
@click.argument("job_name")
@click.pass_context
@async_command
async def quick(ctx, job_name):
    """Quick diagnosis of the most recent failure."""
    settings = ctx.obj["settings"]
    debugger = PipelineDebugger(settings=settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Running quick diagnosis...", total=None)

        try:
            diagnosis = await debugger.quick_diagnosis(job_name)
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            return

    console.print(diagnosis)


@cli.command()
@click.pass_context
@async_command
async def status(ctx):
    """Show overall Jenkins status summary."""
    settings = ctx.obj["settings"]
    client = JenkinsMCPClient(settings=settings)

    console.print("\n[bold]Jenkins Status Summary[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching status...", total=None)

        # Get running pipelines
        progress.update(task, description="Fetching running pipelines...")
        running_result = await client.get_running_pipelines()
        running_count = len(running_result.content) if running_result.success else 0

        # Get queue
        progress.update(task, description="Fetching queue...")
        queue_result = await client.get_queue()
        queue_count = len(queue_result.content) if queue_result.success else 0

        # Get failures today
        progress.update(task, description="Fetching today's failures...")
        failures_result = await client.get_failed_builds("today")
        failures_count = len(failures_result.content) if failures_result.success else 0

        # Get nodes
        progress.update(task, description="Fetching nodes...")
        nodes_result = await client.get_nodes()
        if nodes_result.success:
            nodes = nodes_result.content
            online_nodes = sum(1 for n in nodes if not n.get("offline"))
            total_nodes = len(nodes)
        else:
            online_nodes = 0
            total_nodes = 0

    # Display summary
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Running Pipelines", f"[yellow]{running_count}[/yellow]")
    table.add_row("Queue Size", f"[blue]{queue_count}[/blue]")
    table.add_row("Failures Today", f"[red]{failures_count}[/red]" if failures_count > 0 else f"[green]{failures_count}[/green]")
    table.add_row("Nodes Online", f"[green]{online_nodes}[/green]/{total_nodes}")

    console.print(table)

    if failures_count > 0:
        console.print(f"\n[yellow]Tip:[/yellow] Run 'pg failures' to see failed jobs, then 'pg debug <job>' to analyze.")


def main():
    """Entry point for CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
