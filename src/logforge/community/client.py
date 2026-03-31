"""Community API client for LogForge Templates Registry."""

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logforge.utils.logging import get_logger
from logforge.telemetry import get_actor_id

logger = get_logger(__name__)


class CommunityAPIError(Exception):
    """Base exception for Community API errors."""
    pass


class CommunityAPINotFoundError(CommunityAPIError):
    """Template or resource not found in registry."""
    pass


class CommunityAPIRateLimitError(CommunityAPIError):
    """Rate limit exceeded."""
    pass


class CommunityAPIClient:
    """HTTP client for LogForge Templates Registry API.
    
    Provides methods to interact with the Templates-UI API:
    - List vendors
    - Search templates
    - Get template details
    - Download vendor packages
    """
    
    def __init__(
        self,
        base_url: str = "https://logforge.io/api/v1",  # Default matches Templates-UI deployment
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize Community API client.
        
        Args:
            base_url: Base URL for Templates-UI API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'LogForge-OSS/1.0.0',
            'Accept': 'application/json',
        })
        # Mark requests as originating from the CLI for server-side telemetry attribution.
        self.session.headers.update({
            "X-LogForge-Client": "cli",
            "X-LogForge-Actor-Id": get_actor_id(),
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request to API endpoint.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            CommunityAPINotFoundError: If resource not found (404)
            CommunityAPIRateLimitError: If rate limited (429)
            CommunityAPIError: For other API errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"API request: {method} {url}")
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Retry after {retry_after} seconds")
                raise CommunityAPIRateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )
            
            # Handle not found
            if response.status_code == 404:
                raise CommunityAPINotFoundError(f"Resource not found: {url}")
            
            # Handle other errors
            response.raise_for_status()
            
            # Parse JSON response
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            raise CommunityAPIError(f"Request timeout: {url}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise CommunityAPIError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise CommunityAPIError(f"Request failed: {e}")
    
    def get_health(self) -> Dict[str, Any]:
        """Get API health status.
        
        Returns:
            Health check response with status, counts, sync info
        """
        return self._request("GET", "/health")
    
    def get_vendors(self) -> List[Dict[str, Any]]:
        """Get list of all vendors from registry.
        
        Returns:
            List of vendor dictionaries with id, vendor, description, etc.
        """
        return self._request("GET", "/vendors")
    
    def get_vendor_detail(self, vendor_id: str) -> Dict[str, Any]:
        """Get detailed vendor information.
        
        Args:
            vendor_id: Vendor identifier (e.g., "microsoft")
            
        Returns:
            Vendor details including products list
        """
        return self._request("GET", f"/vendors/{vendor_id}")
    
    def get_product_detail(
        self,
        vendor_id: str,
        product_id: str
    ) -> Dict[str, Any]:
        """Get product details including data sources.
        
        Args:
            vendor_id: Vendor identifier
            product_id: Product identifier
            
        Returns:
            Product details with data sources and templates
        """
        return self._request("GET", f"/vendors/{vendor_id}/{product_id}")
    
    def get_data_source_detail(
        self,
        vendor_id: str,
        product_id: str,
        data_source_id: str
    ) -> Dict[str, Any]:
        """Get data source details including templates.
        
        Args:
            vendor_id: Vendor identifier
            product_id: Product identifier
            data_source_id: Data source identifier
            
        Returns:
            Data source details with templates list
        """
        return self._request(
            "GET",
            f"/vendors/{vendor_id}/{product_id}/{data_source_id}"
        )
    
    def get_template_detail(
        self,
        vendor_id: str,
        product_id: str,
        data_source_id: str,
        template_id: str
    ) -> Dict[str, Any]:
        """Get detailed template information.
        
        Args:
            vendor_id: Vendor identifier
            product_id: Product identifier
            data_source_id: Data source identifier
            template_id: Template identifier (event type)
            
        Returns:
            Template details including metadata and version
        """
        return self._request(
            "GET",
            f"/vendors/{vendor_id}/{product_id}/{data_source_id}/{template_id}"
        )
    
    def search_templates(
        self,
        query: Optional[str] = None,
        vendor_id: Optional[str] = None,
        product_id: Optional[str] = None,
        data_source_id: Optional[str] = None,
        template_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Search templates with query and filters.
        
        Args:
            query: Search query (searches vendor/product/template names/descriptions)
            vendor_id: Filter by vendor
            product_id: Filter by product
            data_source_id: Filter by data source
            template_id: Filter by template
            page: Page number (default: 1)
            page_size: Results per page (default: 10, max: 100)
            
        Returns:
            Hierarchical template tree with vendors/products/data_sources/templates
        """
        params = {
            "page": page,
            "page_size": min(page_size, 100),  # Cap at 100
        }
        
        if query:
            params["q"] = query
        if vendor_id:
            params["vendor_id"] = vendor_id
        if product_id:
            params["product_id"] = product_id
        if data_source_id:
            params["data_source_id"] = data_source_id
        if template_id:
            params["template_id"] = template_id
        
        return self._request("GET", "/community-templates", params=params)
    
    def download_vendor_package(
        self,
        vendor_id: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download vendor package (.forge file).
        
        Args:
            vendor_id: Vendor identifier
            output_path: Path to save downloaded package
            progress_callback: Optional callback for download progress
                Callback signature: callback(bytes_downloaded, total_bytes)
            
        Returns:
            Path to downloaded file
            
        Raises:
            CommunityAPINotFoundError: If vendor not found
            CommunityAPIError: For download errors
        """
        url = f"{self.base_url}/vendors/{vendor_id}/download"
        
        try:
            logger.info(f"Downloading vendor package: {vendor_id}")
            
            # Stream download for large files
            response = self.session.get(url, stream=True, timeout=self.timeout)
            
            # Handle errors
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise CommunityAPIRateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )
            
            if response.status_code == 404:
                raise CommunityAPINotFoundError(f"Vendor not found: {vendor_id}")
            
            response.raise_for_status()
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Determine file size from Content-Length header
            total_size = int(response.headers.get('Content-Length', 0))
            bytes_downloaded = 0
            
            # Write file with progress tracking
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_size)
            
            logger.info(f"Downloaded package: {output_path} ({bytes_downloaded} bytes)")
            return output_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Download failed: {e}")
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()
            raise CommunityAPIError(f"Download failed: {e}")
    
    def wait_for_rate_limit(self, retry_after: int) -> None:
        """Wait for rate limit to reset.
        
        Args:
            retry_after: Seconds to wait
        """
        logger.info(f"Waiting {retry_after} seconds for rate limit reset...")
        time.sleep(retry_after)

