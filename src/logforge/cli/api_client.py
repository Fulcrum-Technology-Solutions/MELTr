"""API client for CLI commands."""

import os
from typing import Optional

import requests
import typer
from rich.console import Console

console = Console()


class APIClient:
    """Client for communicating with LogForge management API."""
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 5
    ) -> None:
        """Initialize API client.
        
        Args:
            api_url: Base URL for API. Defaults to environment variable or localhost:8080
            api_key: API key for authentication. Defaults to environment variable
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or os.getenv('LOGFORGE_API_URL', 'http://127.0.0.1:8080')
        self.api_key = api_key or os.getenv('LOGFORGE_API_KEY')
        self.timeout = timeout
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
    
    def check_health(self) -> bool:
        """Check if API is healthy and service is running.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = self.session.get(
                f'{self.api_url}/api/health',
                timeout=self.timeout
            )
            return response.status_code == 200
        except (requests.RequestException, requests.Timeout):
            return False
    
    def require_service_running(self) -> None:
        """Require that the service is running, exit if not.
        
        Raises:
            typer.Exit: If service is not running
        """
        if not self.check_health():
            console.print("[red]✗ ERROR: SERVICE_NOT_RUNNING[/red]")
            console.print("[yellow]Hint: start the service first → sudo systemctl start logforge[/yellow]")
            raise typer.Exit(code=1)
    
    def get(self, endpoint: str, timeout: Optional[int] = None, **kwargs) -> requests.Response:
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
        url = f'{self.api_url}{endpoint}'
        request_timeout = timeout if timeout is not None else self.timeout
        return self.session.get(url, timeout=request_timeout, **kwargs)
    
    def post(self, endpoint: str, timeout: Optional[int] = None, **kwargs) -> requests.Response:
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
        url = f'{self.api_url}{endpoint}'
        request_timeout = timeout if timeout is not None else self.timeout
        return self.session.post(url, timeout=request_timeout, **kwargs)


def get_api_client(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> APIClient:
    """Get API client instance.
    
    Args:
        api_url: Optional API URL override
        api_key: Optional API key override
        
    Returns:
        APIClient instance
    """
    return APIClient(api_url=api_url, api_key=api_key)

