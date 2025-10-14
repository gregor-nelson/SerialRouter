
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Try to import winreg for Windows registry access
try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


class PortType(Enum):
    """Port type classification"""
    PHYSICAL = "Physical"
    MOXA_VIRTUAL = "Moxa Virtual"
    COM0COM_VIRTUAL = "com0com Virtual"
    OTHER_VIRTUAL = "Other Virtual"
    UNKNOWN = "Unknown"


@dataclass
class SerialPortInfo:
    """Information about a detected serial port"""
    port_name: str
    device_name: str
    port_type: PortType
    registry_key: str
    description: str = ""
    is_moxa: bool = False
    is_available: bool = True
    
    def __str__(self) -> str:
        return f"{self.port_name} ({self.port_type.value}) - {self.description}"


class PortEnumerator:
    """
    Minimal, robust serial port enumerator.
    Focuses on reliability over features - critical for marine operations.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.registry_available = WINREG_AVAILABLE
        
        if not self.registry_available:
            self.logger.warning("Windows registry access not available - port detection will be limited")
    
    def enumerate_ports(self) -> List[SerialPortInfo]:
        """
        Enumerate all available serial ports.
        
        Returns:
            List of SerialPortInfo objects, sorted by port number
        """
        ports = []
        
        if not self.registry_available:
            self.logger.error("Cannot enumerate ports - Windows registry not available")
            return self._get_fallback_ports()
        
        try:
            ports = self._scan_registry_ports()
            self.logger.info(f"Found {len(ports)} serial ports")
            
        except Exception as e:
            self.logger.error(f"Port enumeration failed: {e}")
            ports = self._get_fallback_ports()
        
        return ports
    
    def _scan_registry_ports(self) -> List[SerialPortInfo]:
        """Scan Windows registry for serial ports"""
        ports = []
        
        try:
            # Open the SERIALCOMM registry key
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
            
            # Enumerate all values
            i = 0
            while i < 256:  # Reasonable safety limit
                try:
                    device_name, port_name, _ = winreg.EnumValue(key, i)
                    port_info = self._classify_port(device_name, port_name)
                    ports.append(port_info)
                    i += 1
                    
                except OSError:
                    # No more values
                    break
                except Exception as e:
                    self.logger.warning(f"Error reading registry value {i}: {e}")
                    i += 1
                    continue
            
            winreg.CloseKey(key)
            
        except FileNotFoundError:
            self.logger.warning("SERIALCOMM registry key not found")
        except Exception as e:
            self.logger.error(f"Registry scan failed: {e}")
            raise
        
        # Sort ports by port number for consistent ordering
        ports.sort(key=lambda p: self._port_sort_key(p.port_name))
        return ports
    
    def _classify_port(self, device_name: str, port_name: str) -> SerialPortInfo:
        """
        Classify a port based on its registry device name.
        Conservative classification focusing on Moxa detection.
        """

        # Check for Moxa devices (critical for marine operations)
        if device_name.startswith("Npdrv"):
            return SerialPortInfo(
                port_name=port_name,
                device_name=device_name,
                port_type=PortType.MOXA_VIRTUAL,
                registry_key=device_name,
                description="Moxa RealCOM virtual port",
                is_moxa=True
            )

        # Check for com0com virtual ports (used for outgoing routing)
        if device_name.startswith(r"\Device\com0com"):
            return SerialPortInfo(
                port_name=port_name,
                device_name=device_name,
                port_type=PortType.COM0COM_VIRTUAL,
                registry_key=device_name,
                description="com0com virtual port pair"
            )

        # Check for other virtual port patterns
        device_lower = device_name.lower()
        if any(pattern in device_lower for pattern in ["virtual", "vspd", "cncb", "cnca"]):
            return SerialPortInfo(
                port_name=port_name,
                device_name=device_name,
                port_type=PortType.OTHER_VIRTUAL,
                registry_key=device_name,
                description="Virtual serial port"
            )

        # Default to physical port
        return SerialPortInfo(
            port_name=port_name,
            device_name=device_name,
            port_type=PortType.PHYSICAL,
            registry_key=device_name,
            description="Physical serial port"
        )
    
    def _port_sort_key(self, port_name: str) -> Tuple[int, int]:
        """Generate sort key for port names (COM1, COM2, etc.)"""
        try:
            if port_name.startswith("COM"):
                num = int(port_name[3:])
                return (0, num)  # COM ports first, sorted numerically
            else:
                return (1, 0)    # Other ports last
        except (ValueError, IndexError):
            return (2, 0)        # Invalid port names at end
    
    def _get_fallback_ports(self) -> List[SerialPortInfo]:
        """
        Fallback port list when registry enumeration fails.
        Includes the known fixed ports used by SerialRouter.
        """
        fallback_ports = [
            # Current default incoming port
            SerialPortInfo(
                port_name="",
                device_name="Fallback",
                port_type=PortType.UNKNOWN,
                registry_key="fallback",
                description="Default incoming port (fallback)"
            ),
            # Fixed outgoing ports (likely Moxa virtual ports)
            SerialPortInfo(
                port_name="COM131",
                device_name="Fallback",
                port_type=PortType.MOXA_VIRTUAL,
                registry_key="fallback",
                description="Fixed outgoing port 1 (fallback)",
                is_moxa=True
            ),
            SerialPortInfo(
                port_name="COM141",
                device_name="Fallback",
                port_type=PortType.MOXA_VIRTUAL,
                registry_key="fallback",
                description="Fixed outgoing port 2 (fallback)",
                is_moxa=True
            )
        ]
        
        self.logger.warning("Using fallback port list - enumeration not available")
        return fallback_ports
    
    def get_moxa_ports(self) -> List[SerialPortInfo]:
        """Get only Moxa virtual ports"""
        all_ports = self.enumerate_ports()
        return [port for port in all_ports if port.is_moxa]

    def get_com0com_ports(self) -> List[SerialPortInfo]:
        """Get only com0com virtual ports"""
        all_ports = self.enumerate_ports()
        return [port for port in all_ports if port.port_type == PortType.COM0COM_VIRTUAL]
    
    def get_physical_ports(self) -> List[SerialPortInfo]:
        """Get only physical serial ports"""
        all_ports = self.enumerate_ports()
        return [port for port in all_ports if port.port_type == PortType.PHYSICAL]
    
    def find_port_by_name(self, port_name: str) -> Optional[SerialPortInfo]:
        """Find a specific port by name"""
        all_ports = self.enumerate_ports()
        for port in all_ports:
            if port.port_name.upper() == port_name.upper():
                return port
        return None
    
    def validate_router_ports(self, incoming_port: str, outgoing_ports: List[str]) -> Dict[str, bool]:
        """
        Validate that the required ports exist for SerialRouter operation.

        Args:
            incoming_port: The incoming port name (e.g., "COM1", "COM3")
            outgoing_ports: List of outgoing port names (e.g., ["COM131", "COM141"])

        Returns:
            Dictionary with port names as keys and availability as boolean values
        """
        validation_results = {}
        all_ports = self.enumerate_ports()
        available_port_names = {port.port_name.upper() for port in all_ports}
        
        # Check incoming port
        validation_results[incoming_port] = incoming_port.upper() in available_port_names
        
        # Check outgoing ports
        for outgoing_port in outgoing_ports:
            validation_results[outgoing_port] = outgoing_port.upper() in available_port_names
        
        return validation_results
    
    def get_port_recommendations(self) -> Dict[str, List[str]]:
        """
        Get port recommendations for SerialRouter configuration.
        
        Returns:
            Dictionary with 'incoming' and 'outgoing' port recommendations
        """
        all_ports = self.enumerate_ports()
        
        # Separate by type
        physical_ports = [p.port_name for p in all_ports if p.port_type == PortType.PHYSICAL]
        moxa_ports = [p.port_name for p in all_ports if p.is_moxa]
        
        recommendations = {
            'incoming': physical_ports + [p.port_name for p in all_ports if not p.is_moxa],
            'outgoing': moxa_ports  # Prefer Moxa ports for outgoing (network routing)
        }
        
        return recommendations


def main():
    """Test the port enumerator independently"""
    import sys
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    logger = logging.getLogger('PortEnumeratorTest')
    
    print("SerialRouter Port Enumerator Test")
    print("=" * 50)
    
    # Test port enumeration
    enumerator = PortEnumerator(logger)
    
    try:
        # Get all ports
        all_ports = enumerator.enumerate_ports()
        print(f"\nFound {len(all_ports)} total ports:")
        for port in all_ports:
            print(f"  {port}")
        
        # Get Moxa ports specifically
        moxa_ports = enumerator.get_moxa_ports()
        print(f"\nMoxa virtual ports ({len(moxa_ports)}):")
        for port in moxa_ports:
            print(f"  {port.port_name} - {port.description}")
        
        # Test example SerialRouter configuration
        print(f"\nValidating example SerialRouter ports:")
        # Use first available port as example incoming port
        example_incoming = all_ports[0].port_name if all_ports else "COM1"
        validation = enumerator.validate_router_ports(example_incoming, ["COM131", "COM141"])
        for port_name, is_available in validation.items():
            status = "[OK] Available" if is_available else "[!] Not found"
            print(f"  {port_name}: {status}")
        
        # Get recommendations
        recommendations = enumerator.get_port_recommendations()
        print(f"\nPort recommendations:")
        print(f"  Incoming ports: {recommendations['incoming'][:5]}")  # Show first 5
        print(f"  Outgoing ports: {recommendations['outgoing']}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
    
    print("\nPort enumeration test completed successfully.")


if __name__ == "__main__":
    main()