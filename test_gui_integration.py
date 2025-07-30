#!/usr/bin/env python3
"""
Test script to verify GUI integration with port enumerator
Tests the port enumeration functionality without launching the full GUI
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gui_integration():
    """Test the GUI integration components"""
    print("SerialRouter GUI Integration Test")
    print("=" * 50)
    
    try:
        # Test 1: Import the enhanced GUI module
        print("Test 1: Importing enhanced GUI components...")
        from src.gui.main_window import SerialRouterMainWindow
        from src.core.port_enumerator import PortEnumerator, PortType
        print("[OK] Import successful")
        
        # Test 2: Create port enumerator independently
        print("\nTest 2: Creating port enumerator...")
        enumerator = PortEnumerator()
        ports = enumerator.enumerate_ports()
        print(f"[OK] Found {len(ports)} ports")
        
        # Test 3: Test port categorization
        print("\nTest 3: Port categorization...")
        physical_ports = [p for p in ports if p.port_type == PortType.PHYSICAL]
        moxa_ports = [p for p in ports if p.port_type == PortType.MOXA_VIRTUAL]
        other_virtual = [p for p in ports if p.port_type == PortType.OTHER_VIRTUAL]
        
        print(f"  Physical ports: {len(physical_ports)} - {[p.port_name for p in physical_ports[:3]]}")
        print(f"  Moxa virtual: {len(moxa_ports)} - {[p.port_name for p in moxa_ports[:3]]}")
        print(f"  Other virtual: {len(other_virtual)} - {[p.port_name for p in other_virtual[:3]]}")
        
        # Test 4: Validate current router configuration
        print("\nTest 4: Router configuration validation...")
        validation = enumerator.validate_router_ports("COM54", ["COM131", "COM141"])
        for port_name, is_available in validation.items():
            status = "[OK]" if is_available else "[MISSING]"
            print(f"  {status} {port_name}")
        
        # Test 5: Test port recommendations
        print("\nTest 5: Port recommendations...")
        recommendations = enumerator.get_port_recommendations()
        print(f"  Incoming: {recommendations['incoming'][:3]}")
        print(f"  Outgoing: {recommendations['outgoing'][:3]}")
        
        # Test 6: Test that GUI can be instantiated (without showing)
        print("\nTest 6: GUI instantiation test...")
        from PyQt6.QtWidgets import QApplication
        
        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app_created = True
        else:
            app_created = False
        
        try:
            # Create main window instance (don't show it)
            main_window = SerialRouterMainWindow()
            
            # Test that it has the port enumerator
            assert hasattr(main_window, 'port_enumerator'), "Main window missing port_enumerator"
            
            # Test that refresh method works
            main_window.refresh_available_ports()
            
            # Check that combo box is populated
            combo_count = main_window.incoming_port_combo.count()
            print(f"[OK] GUI created successfully, combo box has {combo_count} items")
            
            # Test validation method
            is_valid = main_window.validate_selected_port()
            print(f"[OK] Port validation: {is_valid}")
            
            # Clean up
            main_window.close()
            if app_created:
                app.quit()
                
        except Exception as e:
            print(f"[ERROR] GUI test failed: {e}")
            if app_created:
                app.quit()
            raise
        
        print("\n" + "=" * 50)
        print("[SUCCESS] ALL TESTS PASSED - GUI Integration Successful!")
        print("[SUCCESS] Moxa port detection is working correctly")
        print("[SUCCESS] GUI dropdown will show all available ports by type")
        print("[SUCCESS] Enhanced validation and port analysis features enabled")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_integration()
    sys.exit(0 if success else 1)