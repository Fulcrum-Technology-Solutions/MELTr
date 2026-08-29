"""Entity registry with in-memory cache and lookup functions."""

import random
from typing import Any, Dict, List, Optional

from meltr.core.config import Config
from meltr.entities.storage import EntityStorage
from meltr.entities.validator import validate_entities
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class EntityRegistry:
    """Manages entity registry with in-memory cache and template-accessible functions."""
    
    def __init__(self, config: Config) -> None:
        """Initialize entity registry.
        
        Args:
            config: Configuration object
        """
        self.config = config
        registry_config = config.entity_registry
        
        self.storage = EntityStorage(
            auto_save=registry_config.auto_save,
            save_interval=registry_config.save_interval,
            backup_enabled=registry_config.backup_enabled,
            backup_count=registry_config.backup_count,
        )
        
        # In-memory cache
        self._data: Optional[Dict[str, Any]] = None
        self._users_by_username: Dict[str, Dict[str, Any]] = {}
        self._devices_by_hostname: Dict[str, Dict[str, Any]] = {}
        self._services_by_name: Dict[str, Dict[str, Any]] = {}
        
        # Load initial data (allow empty for service startup)
        self.reload(strict=False)
        
        # Start auto-save if enabled
        if registry_config.auto_save:
            self.storage.start_auto_save(self._get_data_for_save)
    
    def _get_data_for_save(self) -> Dict[str, Any]:
        """Get current data for auto-save."""
        return self._data or {}
    
    def reload(self, strict: bool = True) -> None:
        """Reload entities from disk.
        
        Args:
            strict: If True, requires at least one entity of each type. If False, allows empty lists.
        """
        try:
            self._data = self.storage.load(strict=strict)
            self._rebuild_indexes()
            logger.info("Entity registry reloaded from disk")
        except FileNotFoundError:
            logger.warning("Entities file not found, using empty registry")
            self._data = {
                'organization': {'name': 'Unknown', 'domain': 'unknown.com'},
                'users': [],
                'devices': [],
                'services': [],
            }
            self._rebuild_indexes()
        except Exception as e:
            logger.error(f"Failed to load entities: {e}", exc_info=True)
            # Try to load backup
            try:
                backup_data = self.storage.load_backup(1)
                if backup_data:
                    logger.info("Loaded entities from backup")
                    self._data = backup_data
                    self._rebuild_indexes()
                else:
                    raise
            except Exception:
                raise
    
    def _rebuild_indexes(self) -> None:
        """Rebuild in-memory indexes for fast lookups."""
        if not self._data:
            return
        
        # Index users by username (case-insensitive)
        self._users_by_username = {}
        for user in self._data.get('users', []):
            username = user.get('username', '').lower()
            self._users_by_username[username] = user
        
        # Index devices by hostname
        self._devices_by_hostname = {}
        for device in self._data.get('devices', []):
            hostname = device.get('hostname', '')
            self._devices_by_hostname[hostname] = device
        
        # Index services by name
        self._services_by_name = {}
        for service in self._data.get('services', []):
            name = service.get('name', '')
            self._services_by_name[name] = service
    
    def save(self) -> None:
        """Save entities to disk."""
        if self._data:
            self.storage.save(self._data)
    
    def get_organization(self) -> Dict[str, Any]:
        """Get organization data.
        
        Returns:
            Organization dictionary
        """
        return self._data.get('organization', {}) if self._data else {}
    
    def get_organization_field(self, field: str) -> Any:
        """Get specific organization field, supporting dot notation.
        
        Args:
            field: Field name, supports dot notation (e.g., 'contacts.admin')
            
        Returns:
            Field value or None if not found
        """
        org = self.get_organization()
        if not org:
            return None
        
        # Support dot notation for nested fields
        parts = field.split('.')
        value = org
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value
    
    def get_organization_contact(self, role: str) -> Optional[str]:
        """Get organization contact for specified role.
        
        Args:
            role: Contact role (e.g., 'admin', 'security')
            
        Returns:
            Contact email/string or None
        """
        contacts = self.get_organization_field('contacts')
        if isinstance(contacts, dict):
            return contacts.get(role)
        return None
    
    def get_organization_timezone(self) -> str:
        """Get organization timezone.
        
        Returns:
            Timezone string (e.g., 'America/New_York') or 'UTC' if not specified
        """
        timezone = self.get_organization_field('timezone')
        if timezone and isinstance(timezone, str):
            return timezone
        return 'UTC'
    
    def get_random_user(self) -> Optional[Dict[str, Any]]:
        """Get random user from registry.
        
        Returns:
            Random user dictionary or None if no users
        """
        users = self._data.get('users', []) if self._data else []
        if not users:
            return None
        return random.choice(users)
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """Get specific user by username (case-insensitive).
        
        Args:
            username: Username to lookup
            
        Returns:
            User dictionary
            
        Raises:
            KeyError: If user not found
        """
        username_lower = username.lower()
        if username_lower not in self._users_by_username:
            raise KeyError(f"User not found: {username}")
        return self._users_by_username[username_lower]
    
    def get_random_device(self) -> Optional[Dict[str, Any]]:
        """Get random device from registry.
        
        Returns:
            Random device dictionary or None if no devices
        """
        devices = self._data.get('devices', []) if self._data else []
        if not devices:
            return None
        return random.choice(devices)
    
    def get_device(self, hostname: str) -> Dict[str, Any]:
        """Get specific device by hostname.
        
        Args:
            hostname: Hostname to lookup
            
        Returns:
            Device dictionary
            
        Raises:
            KeyError: If device not found
        """
        if hostname not in self._devices_by_hostname:
            raise KeyError(f"Device not found: {hostname}")
        return self._devices_by_hostname[hostname]
    
    def get_random_service(self) -> Optional[Dict[str, Any]]:
        """Get random service from registry.
        
        Returns:
            Random service dictionary or None if no services
        """
        services = self._data.get('services', []) if self._data else []
        if not services:
            return None
        return random.choice(services)
    
    def get_service(self, name: str) -> Dict[str, Any]:
        """Get specific service by name.
        
        Args:
            name: Service name to lookup
            
        Returns:
            Service dictionary
            
        Raises:
            KeyError: If service not found
        """
        if name not in self._services_by_name:
            raise KeyError(f"Service not found: {name}")
        return self._services_by_name[name]
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users.
        
        Returns:
            List of user dictionaries
        """
        return self._data.get('users', []) if self._data else []
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all devices.
        
        Returns:
            List of device dictionaries
        """
        return self._data.get('devices', []) if self._data else []
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all services.
        
        Returns:
            List of service dictionaries
        """
        return self._data.get('services', []) if self._data else []
    
    def get_network_ranges(self) -> List[Dict[str, Any]]:
        """Get network ranges configuration.
        
        Returns:
            List of network range definitions
        """
        return self._data.get('network_ranges', []) if self._data else []
    
    def close(self) -> None:
        """Close registry and stop auto-save."""
        self.storage.stop_auto_save()
        # Final save
        if self._data:
            self.storage.save(self._data)

