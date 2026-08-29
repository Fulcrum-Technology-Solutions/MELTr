"""Interactive entity editor assistant."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.table import Table

from meltr.core.paths import get_entities_path, get_logforge_home
from meltr.entities.storage import EntityStorage
from meltr.entities.validator import validate_entities

console = Console()


def entities_editor() -> None:
    """Interactive entity registry editor."""
    storage = EntityStorage()
    
    try:
        data = storage.load(strict=False)
        console.print("[green]Loaded existing entities[/green]\n")
    except FileNotFoundError:
        console.print("[yellow]No existing entities found. Starting fresh.[/yellow]\n")
        data = _create_default_entities_structure()
    
    while True:
        choice = _show_main_menu(data)
        
        if choice == "1":
            data = _edit_organization(data)
        elif choice == "2":
            data = _edit_users_section(data)
        elif choice == "3":
            data = _edit_devices_section(data)
        elif choice == "4":
            data = _edit_services_section(data)
        elif choice == "5":
            _preview_entities(data)
        elif choice == "6":
            if _save_entities(data, storage):
                console.print("\n[green]✓ Entities saved successfully![/green]")
                break
        elif choice == "7":
            if Confirm.ask("\n[yellow]Discard changes and exit?", default=False):
                break
        else:
            console.print("[red]Invalid choice[/red]")
    
    console.print("\n[dim]Entity editor closed[/dim]")


def _show_main_menu(data: Dict[str, Any]) -> str:
    """Display main entity menu."""
    org = data.get('organization', {})
    org_name = org.get('name', 'Not set')
    
    user_count = len(data.get('users', []))
    device_count = len(data.get('devices', []))
    service_count = len(data.get('services', []))
    
    console.print("\n[bold]LogForge Entity Registry Editor[/bold]\n")
    
    summary = (
        f"[cyan]Organization:[/cyan] {org_name}\n"
        f"[cyan]Users:[/cyan] {user_count}\n"
        f"[cyan]Devices:[/cyan] {device_count}\n"
        f"[cyan]Services:[/cyan] {service_count}"
    )
    console.print(Panel(summary, title="Current Status", border_style="blue"))
    
    menu = Panel(
        "[cyan]1.[/cyan] Edit Organization Info\n"
        "[cyan]2.[/cyan] Manage Users\n"
        "[cyan]3.[/cyan] Manage Devices\n"
        "[cyan]4.[/cyan] Manage Services\n"
        "[cyan]5.[/cyan] Preview Entities\n"
        "[cyan]6.[/cyan] Save and Exit\n"
        "[cyan]7.[/cyan] Exit Without Saving",
        title="Main Menu",
        border_style="blue",
    )
    console.print(menu)
    
    return Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6", "7"], default="6")


def _edit_organization(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit organization information."""
    console.print("\n[bold]Organization Information[/bold]\n")
    
    org = data.setdefault('organization', {})
    
    name = Prompt.ask("Organization name", default=org.get('name', 'Acme Corporation'))
    org['name'] = name
    
    domain = Prompt.ask("Organization domain", default=org.get('domain', 'acme.com'))
    org['domain'] = domain
    
    # Optional fields
    if Confirm.ask("Configure additional organization details?", default=False):
        netbios = Prompt.ask("NetBIOS domain", default=org.get('netbios_domain', ''))
        if netbios:
            org['netbios_domain'] = netbios
        
        timezone = Prompt.ask("Timezone", default=org.get('timezone', 'America/New_York'))
        org['timezone'] = timezone
        
        industry = Prompt.ask("Industry", default=org.get('industry', ''))
        if industry:
            org['industry'] = industry
        
        # Contacts
        if Confirm.ask("Configure contacts?", default=False):
            contacts = org.setdefault('contacts', {})
            contacts['security'] = Prompt.ask("Security contact email", default=contacts.get('security', ''))
            contacts['it_support'] = Prompt.ask("IT support email", default=contacts.get('it_support', ''))
            contacts['helpdesk'] = Prompt.ask("Helpdesk email", default=contacts.get('helpdesk', ''))
    
    console.print("[green]✓ Organization information updated[/green]")
    return data


def _edit_users_section(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit users section."""
    console.print("\n[bold]User Management[/bold]\n")
    
    users = data.setdefault('users', [])
    
    while True:
        if users:
            table = Table(title="Current Users")
            table.add_column("Username", style="cyan")
            table.add_column("Full Name", style="green")
            table.add_column("Email", style="yellow")
            table.add_column("Department", style="magenta")
            
            for user in users:
                table.add_row(
                    user.get('username', ''),
                    user.get('full_name', ''),
                    user.get('email', ''),
                    user.get('department', ''),
                )
            
            console.print(table)
        else:
            console.print("[yellow]No users configured[/yellow]\n")
        
        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add new user")
        if users:
            console.print("  [2] Edit user")
            console.print("  [3] Remove user")
        console.print("  [4] Import users from file")
        console.print("  [5] Back to main menu")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice == "1":
            new_user = _create_user_interactive(users)
            if new_user:
                users.append(new_user)
                console.print(f"[green]✓ Added user: {new_user['username']}[/green]")
        elif choice == "2" and users:
            data = _edit_user_interactive(data)
        elif choice == "3" and users:
            data = _remove_user_interactive(data)
        elif choice == "4":
            data = _import_users_interactive(data)
        elif choice == "5":
            break
    
    return data


def _create_user_interactive(existing_users: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Interactively create a new user."""
    console.print("\n[bold]Create New User[/bold]\n")
    
    # Required fields
    username = Prompt.ask("Username")
    
    # Check for duplicates
    if any(u.get('username') == username for u in existing_users):
        console.print(f"[red]User '{username}' already exists[/red]")
        if not Confirm.ask("Use a different username?", default=True):
            return None
        username = Prompt.ask("Username")
    
    full_name = Prompt.ask("Full name")
    email = Prompt.ask("Email address")
    
    # Validate email format (basic)
    if '@' not in email:
        console.print("[yellow]Warning: Email format may be invalid[/yellow]")
    
    # Optional fields
    user_id = Prompt.ask("User ID (optional)", default="")
    department = Prompt.ask("Department (optional)", default="")
    title = Prompt.ask("Job title (optional)", default="")
    
    is_admin = Confirm.ask("Is admin user?", default=False)
    employee_type = Prompt.ask(
        "Employee type",
        choices=["employee", "contractor", "intern", "vendor"],
        default="employee",
    )
    
    # Location (optional)
    location = None
    if Confirm.ask("Add location information?", default=False):
        location = {
            'city': Prompt.ask("City", default=""),
            'state': Prompt.ask("State/Province", default=""),
            'country': Prompt.ask("Country", default="USA"),
        }
    
    user = {
        'username': username,
        'full_name': full_name,
        'email': email,
        'is_admin': is_admin,
        'employee_type': employee_type,
    }
    
    if user_id:
        user['user_id'] = user_id
    if department:
        user['department'] = department
    if title:
        user['title'] = title
    if location:
        user['location'] = location
    
    return user


def _edit_user_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit an existing user."""
    users = data.get('users', [])
    if not users:
        console.print("[yellow]No users to edit[/yellow]")
        return data
    
    # List users
    console.print("\n[bold]Select User to Edit[/bold]\n")
    for i, user in enumerate(users, 1):
        console.print(f"  [{i}] {user.get('username', '')} - {user.get('full_name', '')}")
    
    choice = IntPrompt.ask("\nSelect user number", default=1)
    if choice < 1 or choice > len(users):
        console.print("[red]Invalid selection[/red]")
        return data
    
    user = users[choice - 1]
    console.print(f"\n[bold]Editing: {user.get('username', '')}[/bold]\n")
    
    # Edit fields
    full_name = Prompt.ask("Full name", default=user.get('full_name', ''))
    user['full_name'] = full_name
    
    email = Prompt.ask("Email", default=user.get('email', ''))
    user['email'] = email
    
    department = Prompt.ask("Department", default=user.get('department', ''))
    if department:
        user['department'] = department
    elif 'department' in user:
        del user['department']
    
    is_admin = Confirm.ask("Is admin?", default=user.get('is_admin', False))
    user['is_admin'] = is_admin
    
    console.print("[green]✓ User updated[/green]")
    return data


def _remove_user_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a user."""
    users = data.get('users', [])
    if not users:
        console.print("[yellow]No users to remove[/yellow]")
        return data
    
    # List users
    console.print("\n[bold]Select User to Remove[/bold]\n")
    for i, user in enumerate(users, 1):
        console.print(f"  [{i}] {user.get('username', '')} - {user.get('full_name', '')}")
    
    choice = IntPrompt.ask("\nSelect user number", default=1)
    if choice < 1 or choice > len(users):
        console.print("[red]Invalid selection[/red]")
        return data
    
    user = users[choice - 1]
    
    if Confirm.ask(f"\n[yellow]Remove user '{user.get('username', '')}'?", default=False):
        users.pop(choice - 1)
        console.print(f"[green]✓ Removed user[/green]")
    
    return data


def _import_users_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Import users from a file."""
    console.print("\n[bold]Import Users[/bold]\n")
    console.print("[yellow]Note: Use 'logforge entities import' command for full import functionality[/yellow]")
    console.print("[yellow]This is a placeholder for future interactive import[/yellow]")
    return data


def _edit_devices_section(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit devices section."""
    console.print("\n[bold]Device Management[/bold]\n")
    
    devices = data.setdefault('devices', [])
    
    while True:
        if devices:
            table = Table(title="Current Devices")
            table.add_column("Hostname", style="cyan")
            table.add_column("IP Address", style="green")
            table.add_column("OS Type", style="yellow")
            table.add_column("Owner", style="magenta")
            
            for device in devices:
                table.add_row(
                    device.get('hostname', ''),
                    device.get('ip_address', ''),
                    device.get('os_type', ''),
                    device.get('owner', ''),
                )
            
            console.print(table)
        else:
            console.print("[yellow]No devices configured[/yellow]\n")
        
        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add new device")
        if devices:
            console.print("  [2] Edit device")
            console.print("  [3] Remove device")
        console.print("  [4] Back to main menu")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            new_device = _create_device_interactive(devices)
            if new_device:
                devices.append(new_device)
                console.print(f"[green]✓ Added device: {new_device['hostname']}[/green]")
        elif choice == "2" and devices:
            data = _edit_device_interactive(data)
        elif choice == "3" and devices:
            data = _remove_device_interactive(data)
        elif choice == "4":
            break
    
    return data


def _create_device_interactive(existing_devices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Interactively create a new device."""
    console.print("\n[bold]Create New Device[/bold]\n")
    
    # Required fields
    hostname = Prompt.ask("Hostname")
    
    # Check for duplicates
    if any(d.get('hostname') == hostname for d in existing_devices):
        console.print(f"[red]Device '{hostname}' already exists[/red]")
        if not Confirm.ask("Use a different hostname?", default=True):
            return None
        hostname = Prompt.ask("Hostname")
    
    ip_address = Prompt.ask("IP address")
    
    # Validate IP (basic)
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
    except ValueError:
        console.print("[yellow]Warning: IP address format may be invalid[/yellow]")
    
    # Optional fields
    os_type = Prompt.ask("OS type (optional)", default="")
    owner = Prompt.ask("Owner (optional)", default="")
    device_type = Prompt.ask(
        "Device type",
        choices=["server", "workstation", "laptop", "mobile", "network", "iot", "other"],
        default="workstation",
    )
    
    # MAC address (required by validator)
    mac_address = Prompt.ask("MAC address (required, format: XX:XX:XX:XX:XX:XX)", default="00:00:00:00:00:00")
    
    device = {
        'hostname': hostname,
        'ip_address': ip_address,
        'mac_address': mac_address,
        'device_type': device_type,
    }
    
    if os_type:
        device['os_type'] = os_type
    if owner:
        device['owner'] = owner
    
    return device


def _edit_device_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit an existing device."""
    devices = data.get('devices', [])
    if not devices:
        console.print("[yellow]No devices to edit[/yellow]")
        return data
    
    # List devices
    console.print("\n[bold]Select Device to Edit[/bold]\n")
    for i, device in enumerate(devices, 1):
        console.print(f"  [{i}] {device.get('hostname', '')} - {device.get('ip_address', '')}")
    
    choice = IntPrompt.ask("\nSelect device number", default=1)
    if choice < 1 or choice > len(devices):
        console.print("[red]Invalid selection[/red]")
        return data
    
    device = devices[choice - 1]
    console.print(f"\n[bold]Editing: {device.get('hostname', '')}[/bold]\n")
    
    # Edit fields
    ip_address = Prompt.ask("IP address", default=device.get('ip_address', ''))
    device['ip_address'] = ip_address
    
    os_type = Prompt.ask("OS type", default=device.get('os_type', ''))
    if os_type:
        device['os_type'] = os_type
    elif 'os_type' in device:
        del device['os_type']
    
    owner = Prompt.ask("Owner", default=device.get('owner', ''))
    if owner:
        device['owner'] = owner
    elif 'owner' in device:
        del device['owner']
    
    console.print("[green]✓ Device updated[/green]")
    return data


def _remove_device_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a device."""
    devices = data.get('devices', [])
    if not devices:
        console.print("[yellow]No devices to remove[/yellow]")
        return data
    
    # List devices
    console.print("\n[bold]Select Device to Remove[/bold]\n")
    for i, device in enumerate(devices, 1):
        console.print(f"  [{i}] {device.get('hostname', '')} - {device.get('ip_address', '')}")
    
    choice = IntPrompt.ask("\nSelect device number", default=1)
    if choice < 1 or choice > len(devices):
        console.print("[red]Invalid selection[/red]")
        return data
    
    device = devices[choice - 1]
    
    if Confirm.ask(f"\n[yellow]Remove device '{device.get('hostname', '')}'?", default=False):
        devices.pop(choice - 1)
        console.print(f"[green]✓ Removed device[/green]")
    
    return data


def _edit_services_section(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit services section."""
    console.print("\n[bold]Service Management[/bold]\n")
    
    services = data.setdefault('services', [])
    
    while True:
        if services:
            table = Table(title="Current Services")
            table.add_column("Name", style="cyan")
            table.add_column("Port", style="green")
            table.add_column("Protocol", style="yellow")
            table.add_column("Description", style="magenta")
            
            for service in services:
                table.add_row(
                    service.get('name', ''),
                    str(service.get('port', '')),
                    service.get('protocol', ''),
                    service.get('description', ''),
                )
            
            console.print(table)
        else:
            console.print("[yellow]No services configured[/yellow]\n")
        
        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add new service")
        if services:
            console.print("  [2] Edit service")
            console.print("  [3] Remove service")
        console.print("  [4] Back to main menu")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            new_service = _create_service_interactive(services)
            if new_service:
                services.append(new_service)
                console.print(f"[green]✓ Added service: {new_service['name']}[/green]")
        elif choice == "2" and services:
            data = _edit_service_interactive(data)
        elif choice == "3" and services:
            data = _remove_service_interactive(data)
        elif choice == "4":
            break
    
    return data


def _create_service_interactive(existing_services: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Interactively create a new service."""
    console.print("\n[bold]Create New Service[/bold]\n")
    
    # Required fields
    name = Prompt.ask("Service name")
    
    # Check for duplicates
    if any(s.get('name') == name for s in existing_services):
        console.print(f"[red]Service '{name}' already exists[/red]")
        if not Confirm.ask("Use a different name?", default=True):
            return None
        name = Prompt.ask("Service name")
    
    port = IntPrompt.ask("Port number")
    
    # Validate port range
    if port < 1 or port > 65535:
        console.print("[red]Port must be between 1 and 65535[/red]")
        return None
    
    protocol = Prompt.ask(
        "Protocol",
        choices=["tcp", "udp", "http", "https", "ftp", "ssh", "telnet", "smtp", "dns", "dhcp", "other"],
        default="tcp",
    )
    
    # Optional fields
    description = Prompt.ask("Description (optional)", default="")
    
    service = {
        'name': name,
        'port': port,
        'protocol': protocol,
    }
    
    if description:
        service['description'] = description
    
    return service


def _edit_service_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit an existing service."""
    services = data.get('services', [])
    if not services:
        console.print("[yellow]No services to edit[/yellow]")
        return data
    
    # List services
    console.print("\n[bold]Select Service to Edit[/bold]\n")
    for i, service in enumerate(services, 1):
        console.print(f"  [{i}] {service.get('name', '')} - {service.get('protocol', '')}/{service.get('port', '')}")
    
    choice = IntPrompt.ask("\nSelect service number", default=1)
    if choice < 1 or choice > len(services):
        console.print("[red]Invalid selection[/red]")
        return data
    
    service = services[choice - 1]
    console.print(f"\n[bold]Editing: {service.get('name', '')}[/bold]\n")
    
    # Edit fields
    port = IntPrompt.ask("Port", default=service.get('port', 80))
    if port < 1 or port > 65535:
        console.print("[red]Invalid port number[/red]")
        return data
    service['port'] = port
    
    protocol = Prompt.ask(
        "Protocol",
        choices=["tcp", "udp", "http", "https", "ftp", "ssh", "telnet", "smtp", "dns", "dhcp", "other"],
        default=service.get('protocol', 'tcp'),
    )
    service['protocol'] = protocol
    
    description = Prompt.ask("Description", default=service.get('description', ''))
    if description:
        service['description'] = description
    elif 'description' in service:
        del service['description']
    
    console.print("[green]✓ Service updated[/green]")
    return data


def _remove_service_interactive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a service."""
    services = data.get('services', [])
    if not services:
        console.print("[yellow]No services to remove[/yellow]")
        return data
    
    # List services
    console.print("\n[bold]Select Service to Remove[/bold]\n")
    for i, service in enumerate(services, 1):
        console.print(f"  [{i}] {service.get('name', '')} - {service.get('protocol', '')}/{service.get('port', '')}")
    
    choice = IntPrompt.ask("\nSelect service number", default=1)
    if choice < 1 or choice > len(services):
        console.print("[red]Invalid selection[/red]")
        return data
    
    service = services[choice - 1]
    
    if Confirm.ask(f"\n[yellow]Remove service '{service.get('name', '')}'?", default=False):
        services.pop(choice - 1)
        console.print(f"[green]✓ Removed service[/green]")
    
    return data


def _preview_entities(data: Dict[str, Any]) -> None:
    """Preview current entities."""
    console.print("\n[bold]Entities Preview[/bold]\n")
    
    output = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    from rich.syntax import Syntax
    syntax = Syntax(output, "yaml", theme="monokai")
    console.print(syntax)


def _save_entities(data: Dict[str, Any], storage: EntityStorage) -> bool:
    """Save entities with validation and confirmation."""
    # Validate before saving
    try:
        validate_entities(data)
    except ValueError as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        if not Confirm.ask("Save anyway?", default=False):
            return False
    
    _preview_entities(data)
    
    if not Confirm.ask("\n[yellow]Save entities?", default=True):
        return False
    
    try:
        storage.save(data)
        return True
    except Exception as e:
        console.print(f"[red]Error saving entities: {e}[/red]")
        return False


def _create_default_entities_structure() -> Dict[str, Any]:
    """Create default entities structure."""
    return {
        'organization': {
            'name': 'Acme Corporation',
            'domain': 'acme.com',
        },
        'users': [],
        'devices': [],
        'services': [],
    }

