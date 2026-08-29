"""Shared interactive CLI menu helpers (pagination, navigation)."""

from typing import Any

from rich.console import Console
from rich.prompt import Prompt


def paginate_choose(
    items: list[tuple[str, Any]],
    *,
    console: Console,
    page_size: int = 20,
    title: str = "",
    show_index: bool = True,
) -> int | None:
    """Paginated list; user picks by global 1-based index or navigation keys.

    Returns:
        Selected index (0-based), ``None`` if quit (``q``), or ``-1`` for back (``b``).
    """
    if not items:
        return None

    total_pages = (len(items) + page_size - 1) // page_size
    current_page = 0

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(items))
        page_items = items[start_idx:end_idx]

        if title:
            console.print(f"\n[bold]{title}[/bold]\n")

        for i, (display_text, _value) in enumerate(page_items):
            idx = start_idx + i
            if show_index:
                console.print(f"  [{idx + 1}] {display_text}")
            else:
                console.print(f"  {display_text}")

        if total_pages > 1:
            console.print(
                f"\n[dim]Page {current_page + 1} of {total_pages} "
                f"(n=next, p=prev, b=back, q=quit)[/dim]"
            )
        else:
            console.print("\n[dim](b=back, q=quit)[/dim]")

        user_input = Prompt.ask("\nSelect option", default="1").strip().lower()

        if user_input == "q":
            return None
        if user_input == "b":
            return -1
        if user_input == "n" and current_page < total_pages - 1:
            current_page += 1
            continue
        if user_input == "p" and current_page > 0:
            current_page -= 1
            continue

        try:
            choice = int(user_input)
            if 1 <= choice <= len(items):
                return choice - 1
            console.print(f"[red]Invalid selection. Please choose 1-{len(items)}[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number, 'n', 'p', 'b', or 'q'[/red]")
