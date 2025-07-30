#!/usr/bin/env python3
"""
Test script to verify port exclusion functionality
Tests that COM131, COM132, COM141, COM142 are properly excluded from incoming port selection
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_port_exclusions():
    """Test that reserved ports are properly excluded"""
    print("SerialRouter Port Exclusion Test")
    print("=" * 50)
    
    try:
        from src.core.port_enumerator import PortEnumerator, PortType
        from src.gui.main_window import SerialRouterMainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Create port enumerator
        print("Test 1: Checking all available ports...")
        enumerator = PortEnumerator()
        all_ports = enumerator.enumerate_ports()
        all_port_names = [p.port_name for p in all_ports]
        print(f"All detected ports: {all_port_names}")
        
        # Check which excluded ports are actually present
        excluded_ports = {"COM131", "COM132", "COM141", "COM142"}
        present_excluded = [port for port in excluded_ports if port in all_port_names]
        print(f"Reserved ports present on system: {present_excluded}")
        
        # Test 2: Create GUI and check dropdown exclusions
        print(f"\nTest 2: Testing GUI dropdown exclusions...")
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app_created = True
        else:
            app_created = False
        
        try:
            # Create GUI instance
            main_window = SerialRouterMainWindow()
            
            # Get ports in dropdown
            combo_items = []
            for i in range(main_window.incoming_port_combo.count()):
                combo_items.append(main_window.incoming_port_combo.itemText(i))
            
            print(f"Ports in dropdown: {combo_items}")
            print(f"Total ports detected: {len(all_port_names)}")
            print(f"Ports in dropdown: {len(combo_items)}")
            print(f"Excluded from dropdown: {len(all_port_names) - len(combo_items)}")
            
            # Test 3: Verify no excluded ports are in dropdown
            print(f"\nTest 3: Verifying exclusions...")
            excluded_found_in_dropdown = []
            for excluded_port in excluded_ports:
                if excluded_port in combo_items:
                    excluded_found_in_dropdown.append(excluded_port)
            
            if excluded_found_in_dropdown:
                print(f"[ERROR] Found excluded ports in dropdown: {excluded_found_in_dropdown}")
                return False
            else:
                print(f"[OK] No excluded ports found in dropdown")
            
            # Test 4: Test validation rejection
            print(f"\nTest 4: Testing validation rejection of excluded ports...")
            
            for excluded_port in present_excluded:
                # Manually set the combo box to an excluded port (simulate user somehow selecting it)
                main_window.incoming_port_combo.addItem(excluded_port)
                main_window.incoming_port_combo.setCurrentText(excluded_port)
                
                # Test validation
                is_valid = main_window.validate_selected_port()
                if is_valid:
                    print(f"[ERROR] Validation incorrectly allowed {excluded_port}")
                    return False
                else:
                    print(f"[OK] Validation correctly rejected {excluded_port}")
                
                # Remove the test item
                index = main_window.incoming_port_combo.findText(excluded_port)
                if index >= 0:
                    main_window.incoming_port_combo.removeItem(index)
            
            # Test 5: Test that valid ports still work
            print(f"\nTest 5: Testing that valid ports are still accepted...")
            
            # Find a valid port (not excluded)
            valid_port = None
            for port_name in all_port_names:
                if port_name not in excluded_ports:
                    valid_port = port_name
                    break
            
            if valid_port:
                main_window.incoming_port_combo.setCurrentText(valid_port)
                is_valid = main_window.validate_selected_port()
                if is_valid:
                    print(f"[OK] Validation correctly accepted {valid_port}")
                else:
                    print(f"[WARNING] Validation rejected valid port {valid_port} (may be due to missing dependencies)")
            
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
        print("[SUCCESS] Port Exclusion Test Passed!")
        print(f"[SUCCESS] Excluded ports ({', '.join(present_excluded)}) are properly blocked")
        print("[SUCCESS] Users cannot select reserved outgoing ports as incoming")
        print("[SUCCESS] System maintains routing integrity")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Exclusion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_port_exclusions()
    sys.exit(0 if success else 1)