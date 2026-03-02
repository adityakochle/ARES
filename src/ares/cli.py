"""ARES Command-line interface."""

import typer
import logging
from pathlib import Path
from typing import Optional
import gc
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ares.config import settings
from ares.ingestion import PDFProcessor, DocumentChunker, DocumentEmbedder
from ares.retrieval import QdrantVectorDB
from ares.agents import ARESDiagnosticCrew
from ares.benchmark import ScenarioGenerator, BenchmarkRunner
from ares.schemas import EquipmentSystem, DocumentType

# Setup logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for formatting
console = Console()

app = typer.Typer(
    help="ARES - Autonomous Diagnostic Engine for Maritime Fleet Reliability"
)


@app.command()
def ingest(
    path: str = typer.Option(
        ..., 
        "--path", 
        "-p",
        help="Path to PDF file or directory"
    ),
    equipment: str = typer.Option(
        "main_engine",
        "--equipment",
        "-e",
        help="Equipment system: main_engine, auxiliary_engine, fuel_oil_purifier, purifier_clarifier, steering_gear, pumps_compressors, hvac_refrigeration, boilers, electrical, safety_systems"
    ),
    doc_type: str = typer.Option(
        "manual",
        "--type",
        "-t",
        help="Document type: sop, manual, troubleshooting, safety_bulletin, parts_catalog"
    ),
):
    """Ingest PDF documents into the knowledge base."""
    try:
        console.print("[bold blue]ARES Document Ingestion[/bold blue]")
        
        # Validate inputs
        if equipment not in [e.value for e in EquipmentSystem]:
            console.print(f"[red]Error: Invalid equipment system '{equipment}'[/red]")
            raise typer.Exit(1)
        
        if doc_type not in [d.value for d in DocumentType]:
            console.print(f"[red]Error: Invalid document type '{doc_type}'[/red]")
            raise typer.Exit(1)
        
        # Process PDFs
        pdf_processor = PDFProcessor()
        chunker = DocumentChunker()
        embedder = DocumentEmbedder()
        vector_db = QdrantVectorDB()
        
        input_path = Path(path)
        pdf_files = []
        
        if input_path.is_file() and input_path.suffix.lower() == '.pdf':
            pdf_files = [input_path]
        elif input_path.is_dir():
            pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("**/*.pdf"))
        else:
            console.print(f"[red]Error: Path not found or not a PDF file: {path}[/red]")
            raise typer.Exit(1)
        
        if not pdf_files:
            console.print("[yellow]No PDF files found[/yellow]")
            raise typer.Exit(1)
        
        console.print(f"[green]Found {len(pdf_files)} PDF files[/green]")
        
        # Create Qdrant collection
        console.print("[cyan]Setting up vector database...[/cyan]")
        vector_db.create_collection()
        
        total_chunks = 0

        # Process each PDF using the streaming generator so that scanned PDFs
        # are OCR'd, chunked, embedded, and inserted one page at a time.
        # This keeps RAM constant regardless of document length.
        for pdf_file in pdf_files:
            console.print(f"\n[cyan]Processing: {pdf_file.name}[/cyan]")

            batch_size = settings.embedding_batch_size
            first_page = True

            for page_num, page_data, total_pages, is_text in pdf_processor.iter_pages(str(pdf_file)):
                if first_page:
                    console.print(f"  Pages: {total_pages} ({'text' if is_text else 'scanned'})")
                    first_page = False

                page_chunks = chunker.create_chunks(
                    pages_dict={page_num: page_data},
                    filename=pdf_file.name,
                    equipment_system=EquipmentSystem(equipment),
                    document_type=DocumentType(doc_type),
                    is_text_pdf=is_text,
                )

                # Free page text immediately — chunks hold their own copy
                del page_data
                gc.collect()

                if not page_chunks:
                    continue

                console.print(f"  Page {page_num}/{total_pages} -> {len(page_chunks)} chunks")

                page_inserted = 0
                for start in range(0, len(page_chunks), batch_size):
                    batch = page_chunks[start : start + batch_size]
                    embeddings = embedder.embed_texts([c.text for c in batch])

                    for c, emb in zip(batch, embeddings):
                        c.embedding = emb

                    inserted = vector_db.insert_chunks(batch)
                    page_inserted += inserted
                    total_chunks += inserted

                    for c in batch:
                        c.embedding = None
                    del embeddings, batch
                    gc.collect()

                console.print(f"    [dim]Inserted {page_inserted} chunks (total: {total_chunks})[/dim]")
                del page_chunks
                gc.collect()
        
        console.print(f"\n[green]✓ Ingestion complete![/green]")
        console.print(f"[bold]Total chunks indexed: {total_chunks}[/bold]")
        
        # Show stats
        stats = vector_db.collection_stats()
        console.print("\n[cyan]Vector Database Stats:[/cyan]")
        for key, value in stats.items():
            console.print(f"  {key}: {value}")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Ingestion failed")
        raise typer.Exit(1)


@app.command()
def diagnose(
    fault: str = typer.Option(
        ...,
        "--fault",
        "-f",
        help="Fault description"
    ),
    equipment: Optional[str] = typer.Option(
        None,
        "--equipment",
        "-e",
        help="Equipment involved"
    ),
    cite: bool = typer.Option(
        False,
        "--cite",
        "-c",
        help="Append raw source evidence with exact page numbers after the report",
    ),
):
    """Run diagnostic analysis on a reported fault."""
    try:
        console.print("[bold blue]ARES Diagnostic Engine[/bold blue]")
        console.print(f"\n[cyan]Analyzing fault:[/cyan] {fault}\n")

        # Initialize crew
        crew = ARESDiagnosticCrew()

        # Run diagnostic workflow
        inputs = {
            "fault_description": fault,
            "equipment": equipment or "unknown",
        }

        console.print("[yellow]Running diagnostic workflow...[/yellow]")
        result = crew.crew().kickoff(inputs=inputs)

        # Display results
        console.print("\n[bold green]╭─ ARES DIAGNOSTIC REPORT ─╮[/bold green]")
        console.print(result)
        console.print("[bold green]╰──────────────────────────╯[/bold green]")

        # --cite: run vector search and show the raw retrieved passages with
        # exact page numbers so the engineer can verify every claim directly.
        if cite:
            from ares.ingestion import DocumentEmbedder
            embedder = DocumentEmbedder()
            vector_db = QdrantVectorDB()

            console.print("\n[bold yellow]━━ SOURCE EVIDENCE (for manual verification) ━━[/bold yellow]")
            vec = embedder.embed_single(fault)
            hits = vector_db.search(vec, limit=8, equipment_system=equipment)
            for i, h in enumerate(hits, 1):
                flag = " [SAFETY-CRITICAL]" if h.get("safety_critical") else ""
                console.print(
                    f"\n[cyan][{i}] {h.get('source_file')} — page {h.get('page_number')}"
                    f" | score {h.get('score', 0):.3f}{flag}[/cyan]"
                )
                console.print(h.get("text", "").strip())

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Diagnostic failed")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    equipment: Optional[str] = typer.Option(
        None, "--equipment", "-e", help="Filter by equipment system"
    ),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of results"),
):
    """Search the knowledge base and show source pages."""
    try:
        from ares.ingestion import DocumentEmbedder
        embedder = DocumentEmbedder()
        vector_db = QdrantVectorDB()

        vec = embedder.embed_single(query)
        results = vector_db.search(vec, limit=limit, equipment_system=equipment)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        table = Table(title=f'Results for: "{query}"')
        table.add_column("Page", style="cyan", justify="right")
        table.add_column("Score", style="green", justify="right")
        table.add_column("File", style="dim")
        table.add_column("Safety", justify="center")
        table.add_column("Excerpt", no_wrap=False, max_width=80)

        for r in results:
            safety = "[red]⚠[/red]" if r.get("safety_critical") else ""
            table.add_row(
                str(r.get("page_number", "?")),
                f"{r.get('score', 0):.3f}",
                r.get("source_file", ""),
                safety,
                r.get("text", "")[:200].replace("\n", " "),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def index():
    """Show vector database index status."""
    try:
        console.print("[bold blue]ARES Vector Database Status[/bold blue]\n")
        
        vector_db = QdrantVectorDB()
        stats = vector_db.collection_stats()
        
        if not stats:
            console.print("[yellow]Vector database is empty[/yellow]")
            return
        
        # Create table
        table = Table(title="Index Statistics")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in stats.items():
            table.add_row(str(key), str(value))
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Index status check failed")
        raise typer.Exit(1)


@app.command()
def benchmark(
    action: str = typer.Argument(
        "run",
        help="Action: run, generate, report"
    ),
    count: int = typer.Option(
        150,
        "--count",
        "-c",
        help="Number of scenarios to generate"
    ),
):
    """Run benchmark tests on ARES system."""
    try:
        console.print("[bold blue]ARES Benchmark Suite[/bold blue]\n")
        
        if action == "generate":
            console.print(f"[cyan]Generating {count} test scenarios...[/cyan]")
            scenarios = ScenarioGenerator.generate_default_scenarios()
            
            output_path = "data/benchmarks/scenarios.json"
            ScenarioGenerator.save_scenarios(scenarios, output_path)
            
            console.print(f"[green]✓ Generated {len(scenarios)} scenarios[/green]")
            console.print(f"[cyan]Saved to: {output_path}[/cyan]")
        
        elif action == "run":
            console.print("[cyan]Loading scenarios...[/cyan]")
            scenarios = ScenarioGenerator.load_scenarios(
                "data/benchmarks/scenarios.json"
            )
            
            if not scenarios:
                console.print("[yellow]No scenarios found. Run 'ares benchmark generate' first[/yellow]")
                raise typer.Exit(0)
            
            console.print(f"[cyan]Running {len(scenarios)} scenarios...[/cyan]\n")
            
            crew = ARESDiagnosticCrew()
            runner = BenchmarkRunner(crew)
            metrics = runner.run_benchmark(scenarios)
            
            # Save results
            runner.save_results("data/benchmarks/results.json")
            
            # Display summary
            console.print("\n[bold green]Benchmark Results:[/bold green]")
            table = Table()
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Scenarios", str(metrics.get("total_scenarios", 0)))
            table.add_row("Correct Diagnoses", str(metrics.get("correct_diagnoses", 0)))
            table.add_row("Accuracy", f"{metrics.get('accuracy', 0):.1%}")
            table.add_row("Avg Time (s)", f"{metrics.get('avg_time_seconds', 0):.2f}")
            table.add_row("Safety Violations", str(metrics.get("safety_violations", 0)))
            table.add_row("Avg Confidence", f"{metrics.get('avg_confidence', 0):.2f}")
            
            console.print(table)
        
        elif action == "report":
            console.print("[cyan]Loading results...[/cyan]")
            import json
            results_path = Path("data/benchmarks/results.json")
            
            if not results_path.exists():
                console.print("[yellow]No results found. Run 'ares benchmark run' first[/yellow]")
                raise typer.Exit(0)
            
            with open(results_path) as f:
                results = json.load(f)
            
            console.print("\n[bold green]Benchmark Report:[/bold green]")
            table = Table()
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            for key in ["total_scenarios", "correct_diagnoses", "accuracy", "avg_time_seconds", "safety_violations", "avg_confidence"]:
                if key in results:
                    value = results[key]
                    if isinstance(value, float) and key not in ["accuracy", "avg_confidence"]:
                        value = f"{value:.2f}"
                    elif isinstance(value, float):
                        value = f"{value:.1%}" if key == "accuracy" else f"{value:.2f}"
                    table.add_row(key.replace("_", " ").title(), str(value))
            
            console.print(table)
        
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            raise typer.Exit(1)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Benchmark failed")
        raise typer.Exit(1)


@app.command()
def health():
    """Check ARES system health."""
    try:
        console.print("[bold blue]ARES System Health Check[/bold blue]\n")
        
        checks = []
        
        # Check OpenAI API
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            client.models.list()
            checks.append(("OpenAI API", "✓ Connected", "green"))
        except Exception as e:
            checks.append(("OpenAI API", f"✗ Failed: {str(e)[:50]}", "red"))
        
        # Check Qdrant
        try:
            vector_db = QdrantVectorDB()
            stats = vector_db.collection_stats()
            checks.append(("Qdrant Vector DB", "✓ Connected", "green"))
        except Exception as e:
            checks.append(("Qdrant Vector DB", f"✗ Failed: {str(e)[:50]}", "red"))
        
        # Check Configuration
        checks.append(("Configuration", "✓ Loaded", "green"))
        
        # Display results
        table = Table(title="Health Check Results")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="white")
        
        for component, status, color in checks:
            table.add_row(component, f"[{color}]{status}[/{color}]")
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Health check failed")
        raise typer.Exit(1)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
