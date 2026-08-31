"""API client for CLI commands."""

import os

import requests
import typer
from rich.console import Console
from rich.markup import escape

console = Console()


def _get_default_api_url() -> str:
    """Get default API URL from config file or environment.

    Returns:
        API URL string (e.g., 'http://127.0.0.1:8080')
    """
    # Check environment variable first
    env_url = os.getenv("MELTR_API_URL")
    if env_url:
        return env_url

    # Try to load from config file
    try:
        from meltr.core.config import load_config

        config = load_config(create_if_missing=False)
        host = config.api.host
        port = config.api.port
        return f"http://{host}:{port}"
    except Exception:
        # Fall back to default if config can't be loaded
        return "http://127.0.0.1:8080"


class APIClient:
    """Client for communicating with MELTr management API."""

    def __init__(
        self, api_url: str | None = None, api_key: str | None = None, timeout: int = 5
    ) -> None:
        """Initialize API client.

        Args:
            api_url: Base URL for API. Defaults to environment variable, config file, or localhost:8080
            api_key: API key for authentication. Defaults to environment variable
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or _get_default_api_url()
        self.api_key = api_key or os.getenv("MELTR_API_KEY")
        self.timeout = timeout
        self.session = requests.Session()

        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
            # Transitional client identity
            self.session.headers.setdefault("X-MELTr-Client", "cli")
        else:
            self.session.headers.setdefault("X-MELTr-Client", "cli")

    def check_health(self) -> tuple[bool, str | None]:
        """Check if API is healthy and service is running.

        Returns:
            Tuple of (is_healthy, error_message)
        """
        try:
            response = self.session.get(f"{self.api_url}/api/health", timeout=self.timeout)
            if response.status_code == 200:
                return True, None
            return False, f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError as e:
            error_str = str(e)
            if "Connection refused" in error_str or "refused" in error_str.lower():
                return False, "Connection refused (service may not be running or wrong port)"
            return False, f"Connection error: {error_str}"
        except requests.exceptions.Timeout:
            return False, f"Connection timeout after {self.timeout}s"
        except requests.RequestException as e:
            return False, str(e)

    def require_service_running(self) -> None:
        """Require that the service is running, exit if not.

        Raises:
            typer.Exit: If service is not running
        """
        is_healthy, error_msg = self.check_health()
        if not is_healthy:
            console.print("[red]✗ ERROR: SERVICE_NOT_RUNNING[/red]")
            console.print(f"[dim]Attempted: {self.api_url}/api/health[/dim]")
            if error_msg:
                console.print(f"[dim]Error: {escape(str(error_msg))}[/dim]")
            console.print()
            console.print("[yellow]Troubleshooting:[/yellow]")
            console.print("  1. Check if service is running: sudo systemctl status meltr")
            console.print("  2. Verify API port matches config")
            console.print("  3. Set API URL via environment variable:")
            console.print("     export MELTR_API_URL=http://127.0.0.1:8090")
            console.print("  4. Or use --api-url flag:")
            console.print("     meltr --api-url http://127.0.0.1:8090 generators list")
            raise typer.Exit(code=1)

    def get(self, endpoint: str, timeout: int | None = None, **kwargs) -> requests.Response:
        """Make GET request to API.

        Args:
            endpoint: API endpoint (e.g., '/api/status')
            timeout: Request timeout in seconds (overrides default)
            **kwargs: Additional arguments for requests.get

        Returns:
            Response object

        Raises:
            requests.RequestException: On request failure
        """
        url = f"{self.api_url}{endpoint}"
        request_timeout = timeout if timeout is not None else self.timeout
        return self.session.get(url, timeout=request_timeout, **kwargs)

    def post(self, endpoint: str, timeout: int | None = None, **kwargs) -> requests.Response:
        """Make POST request to API.

        Args:
            endpoint: API endpoint (e.g., '/api/generators/test/start')
            timeout: Request timeout in seconds (overrides default)
            **kwargs: Additional arguments for requests.post

        Returns:
            Response object

        Raises:
            requests.RequestException: On request failure
        """
        url = f"{self.api_url}{endpoint}"
        request_timeout = timeout if timeout is not None else self.timeout
        return self.session.post(url, timeout=request_timeout, **kwargs)


def get_api_client(api_url: str | None = None, api_key: str | None = None) -> APIClient:
    """Get API client instance.

    Args:
        api_url: Optional API URL override
        api_key: Optional API key override

    Returns:
        APIClient instance
    """
    return APIClient(api_url=api_url, api_key=api_key)
