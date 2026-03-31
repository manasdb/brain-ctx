"""
brain-ctx CLI
=============
Commands:
    brain-ctx init      — Generate brain.ctx for current project
    brain-ctx validate  — Validate existing brain.ctx
    brain-ctx show      — Display current brain.ctx contents
    brain-ctx score     — Show AI Score for current project
    brain-ctx propose   — Propose updates based on recent changes
    brain-ctx sign      — Sign brain.ctx with Ed25519 key
    brain-ctx verify    — Verify cryptographic signature
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

app     = typer.Typer(name="brain-ctx", help="brain.ctx — AI Constitution Standard", add_completion=False)
console = Console()


@app.command()
def init(
    path:        str  = typer.Argument(".", help="Project root directory"),
    output:      str  = typer.Option("brain.ctx", "--output", "-o", help="Output file path"),
    silent:      bool = typer.Option(False, "--silent", "-s", help="Skip the optional question"),
    no_comments: bool = typer.Option(False, "--no-comments", help="Write YAML without comments"),
):
    """
    Generate brain.ctx for a project automatically.
    Scans codebase, git history, tests, and dependencies.
    Zero mandatory human input.
    """
    from brain_ctx.generators.auto import AutoGenerator
    from brain_ctx.core import BrainCtx

    project = Path(path).resolve()

    console.print(Panel.fit(
        "[bold cyan]brain.ctx[/bold cyan] — AI Constitution Generator\n"
        "[dim]Scanning your project...[/dim]",
        border_style="cyan",
    ))

    with console.status("[bold green]Scanning codebase...") as status:
        status.update("[bold green]Reading package files...")
        gen = AutoGenerator(project)
        ctx = gen.run(interactive=not silent)

    output_path = project / output
    ctx.save(output_path, include_comments=not no_comments)

    # Show result
    console.print()
    console.print(Panel.fit(
        f"[bold green]✓ brain.ctx generated[/bold green]\n\n"
        f"  [bold]Project:[/bold]   {ctx.identity.get('name', 'Unknown')}\n"
        f"  [bold]Vision:[/bold]    {ctx.identity.get('vision', 'Not inferred')}\n"
        f"  [bold]Rules:[/bold]     {len(ctx.hard_rules)} hard rules detected\n"
        f"  [bold]Output:[/bold]    {output_path}\n\n"
        f"[dim]{ctx.ai_score()}[/dim]",
        border_style="green",
        title="brain.ctx",
    ))


@app.command()
def validate(
    path: str = typer.Argument("brain.ctx", help="Path to brain.ctx file"),
):
    """Validate a brain.ctx file against the official schema."""
    from brain_ctx.core import BrainCtx

    ctx = BrainCtx.load(path)
    valid, errors = ctx.validate()

    if valid:
        console.print(f"[bold green]✓ Valid[/bold green] — {path}")
    else:
        console.print(f"[bold red]✗ Invalid[/bold red] — {path}")
        for error in errors:
            console.print(f"  [red]•[/red] {error}")
        raise typer.Exit(1)


@app.command()
def show(
    path:   str  = typer.Argument("brain.ctx", help="Path to brain.ctx file"),
    format: str  = typer.Option("yaml", "--format", "-f", help="Output format: yaml or json"),
):
    """Display the contents of a brain.ctx file."""
    from brain_ctx.core import BrainCtx

    ctx = BrainCtx.load(path)
    content = ctx.to_yaml() if format == "yaml" else ctx.to_json()
    lang    = "yaml" if format == "yaml" else "json"
    console.print(Syntax(content, lang, theme="monokai", line_numbers=True))


@app.command()
def score(
    path:  str = typer.Argument("brain.ctx", help="Path to brain.ctx file"),
    model: str = typer.Option("claude", "--model", "-m", help="Target model"),
):
    """Display the AI Score acknowledgment line."""
    from brain_ctx.core import BrainCtx

    ctx = BrainCtx.load(path)
    console.print(Panel.fit(
        f"[bold green]{ctx.ai_score()}[/bold green]\n\n"
        f"[dim]Model: {model} | Context: ready[/dim]",
        border_style="green",
        title="AI Score",
    ))


@app.command()
def propose(
    ctx_path:     str = typer.Argument("brain.ctx", help="Path to brain.ctx"),
    project_path: str = typer.Option(".", "--project", "-p", help="Project root"),
):
    """Scan for new patterns and propose brain.ctx updates."""
    from brain_ctx.core import BrainCtx

    ctx       = BrainCtx.load(ctx_path)
    proposals = ctx.propose_update(project_path)

    if not proposals:
        console.print("[green]✓ brain.ctx is up to date. No proposals.[/green]")
        return

    table = Table(title="Proposed Updates", border_style="cyan")
    table.add_column("Field",      style="bold cyan")
    table.add_column("Value",      style="white")
    table.add_column("Confidence", style="green")
    table.add_column("Reason",     style="dim")

    for p in proposals:
        conf = p.get("confidence", 0)
        table.add_row(
            p.get("field", ""),
            str(p.get("value", ""))[:60],
            f"{conf:.0%}",
            p.get("reason", ""),
        )
    console.print(table)


@app.command()
def sign(
    ctx_path: str = typer.Argument("brain.ctx", help="Path to brain.ctx"),
    key_path: str = typer.Option(..., "--key", "-k", help="Path to Ed25519 private key"),
):
    """Sign brain.ctx with an Ed25519 private key."""
    from brain_ctx.core import BrainCtx

    ctx = BrainCtx.load(ctx_path)
    ctx.sign(key_path)
    ctx.save(ctx_path)
    console.print(f"[bold green]✓ Signed[/bold green] — {ctx_path}")


@app.command()
def verify(
    path: str = typer.Argument("brain.ctx", help="Path to brain.ctx"),
):
    """Verify the cryptographic signature of a brain.ctx file."""
    from brain_ctx.core import BrainCtx

    ctx   = BrainCtx.load(path)
    valid = ctx.verify_signature()

    if valid:
        console.print(f"[bold green]✓ Signature valid[/bold green] — {path}")
    else:
        console.print(f"[bold red]✗ Signature invalid or missing[/bold red] — {path}")
        raise typer.Exit(1)




@app.command()
def doctor(
    path:    str  = typer.Argument("brain.ctx", help="Path to brain.ctx"),
    project: str  = typer.Option(".", "--project", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show passing checks too"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run health checks on a brain.ctx file."""
    from brain_ctx.core import BrainCtx
    from brain_ctx.doctors.health import DoctorRunner
    import json as json_mod

    ctx    = BrainCtx.load(path)
    runner = DoctorRunner(ctx, project_root=Path(project))
    report = runner.run()

    if json_output:
        console.print(json_mod.dumps(report.to_dict(), indent=2))
        raise typer.Exit(0 if report.passed else 1)

    report.print(verbose=verbose)
    if not report.passed:
        raise typer.Exit(1)


@app.command()
def diff(
    log_path: str  = typer.Argument(".brain-ctx.log", help="Path to observability log"),
    since:    str  = typer.Option("commit", "--since", "-s",
                                  help="Time window: commit, 1h, 24h, 7d, all"),
    role:     str  = typer.Option("", "--role", "-r", help="Filter by agent role"),
    violations_only: bool = typer.Option(False, "--violations", help="Show only blocked actions"),
    rotate:   bool = typer.Option(False, "--rotate", help="Archive old log entries"),
    verbose:  bool = typer.Option(False, "--verbose", "-v"),
):
    """Show what AI agents have done — human-readable diff of the observability log."""
    from brain_ctx.diff.log_reader import DiffReader
    from datetime import timedelta, datetime, timezone

    reader = DiffReader(Path(log_path))

    if rotate:
        n, archive_path = reader.rotate(keep_days=30)
        console.print(f"[green]✓ Archived {n} entries to {archive_path}[/green]")
        return

    if violations_only:
        report = reader.violations_only()
    elif role:
        report = reader.for_role(role)
    elif since == "commit":
        report = reader.since_commit()
    elif since.endswith("h"):
        report = reader.since_hours(int(since[:-1]))
    elif since.endswith("d"):
        report = reader.since_hours(int(since[:-1]) * 24)
    elif since == "all":
        report = reader.all()
    else:
        report = reader.since_commit()

    report.print(verbose=verbose)


@app.command()
def rules(
    path:    str  = typer.Argument("brain.ctx", help="Path to brain.ctx"),
    env:     str  = typer.Option("", "--env", "-e", help="Evaluate for environment (production/staging/development)"),
    branch:  str  = typer.Option("", "--branch", "-b", help="Evaluate for git branch"),
    all_rules: bool = typer.Option(False, "--all", help="Show all rules including conditional ones"),
):
    """Show active rules for the current (or specified) environment."""
    from brain_ctx.core import BrainCtx
    from brain_ctx.rules.conditional import ConditionalRuleEngine, RuleContext

    ctx    = BrainCtx.load(path)
    engine = ConditionalRuleEngine(ctx)

    if env or branch:
        context = RuleContext(
            env=env or "development",
            branch=branch,
        )
    else:
        context = RuleContext.from_environment()

    active = engine.evaluate(context)
    errors = [r for r in active if r.severity == "ERROR"]
    warns  = [r for r in active if r.severity == "WARN"]

    console.print(f"\n[bold]Active rules[/bold] for env=[cyan]{context.env}[/cyan]"
                  f" branch=[cyan]{context.branch or 'unknown'}[/cyan]\n")

    console.print(f"[bold red]Errors ({len(errors)})[/bold red]")
    for r in errors:
        console.print(f"  [red]✗[/red] {r.rule[:100]}")
        if r.reason:
            console.print(f"    [dim]{r.reason}[/dim]")

    if warns:
        console.print(f"\n[bold yellow]Warnings ({len(warns)})[/bold yellow]")
        for r in warns:
            console.print(f"  [yellow]⚠[/yellow] {r.rule[:100]}")


@app.command()
def resolve(
    path:    str  = typer.Argument("brain.ctx", help="Path to brain.ctx with inherit:"),
    output:  str  = typer.Option("", "--output", "-o", help="Save merged result to file"),
    show:    bool = typer.Option(True, "--show/--no-show", help="Print merged result"),
):
    """Resolve inheritance chain and show the merged brain.ctx."""
    from brain_ctx.core import BrainCtx
    from brain_ctx.inherit.resolver import InheritanceResolver

    ctx      = BrainCtx.load(path)
    resolver = InheritanceResolver(ctx, base_path=Path(path).parent)
    merged   = resolver.resolve()

    if show:
        from rich.syntax import Syntax
        console.print(Syntax(merged.to_yaml(), "yaml", theme="monokai"))

    if output:
        merged.save(output)
        console.print(f"[green]✓ Merged brain.ctx saved to {output}[/green]")

    console.print(f"\n[bold]Merged:[/bold] {len(merged.hard_rules)} rules  "
                  f"{len(merged.trust.get('agents', {}))} agents")


@app.command()
def stacks(
    project: str = typer.Argument(".", help="Project root to scan"),
):
    """Detect tech stacks in a project (shows what brain-ctx init would detect)."""
    from brain_ctx.patterns.library import StackDetector
    from rich.table import Table

    detector = StackDetector(Path(project))
    detected = detector.detect()

    if not detected:
        console.print("[yellow]No stacks detected.[/yellow]")
        return

    table = Table(title=f"Detected stacks in {project}", border_style="cyan")
    table.add_column("Stack",        style="bold cyan")
    table.add_column("Language",     style="white")
    table.add_column("Confidence",   style="green")
    table.add_column("Entry File",   style="dim")
    table.add_column("API Pattern",  style="dim")

    for s in detected:
        table.add_row(
            s.name,
            s.language,
            f"{s.confidence:.0%}",
            s.detected_entry or "(not found)",
            s.api_pattern[:40] + ("..." if len(s.api_pattern) > 40 else ""),
        )

    console.print(table)

def main():
    app()


if __name__ == "__main__":
    main()
