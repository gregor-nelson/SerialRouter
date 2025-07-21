import serial
import threading
import time
import sys

def route_data(source_port, dest_ports, direction):
    """Route data from source to multiple destination ports"""
    bytes_transferred = 0
    
    while True:
        try:
            if source_port.in_waiting > 0:
                data = source_port.read(source_port.in_waiting)
                if data:
                    # Send to all destination ports
                    for dest_port in dest_ports:
                        dest_port.write(data)
                    
                    bytes_transferred += len(data)
                    print(f"{direction}: {len(data)} bytes (Total: {bytes_transferred})")
                    
                    # Show actual data for debugging (first 100 chars)
                    if len(data) < 100:
                        print(f"  Data: {data.decode('ascii', errors='ignore')}")
                    
        except Exception as e:
            print(f"{direction} error: {e}")
            break
        
        time.sleep(0.001)  # Small delay to prevent CPU spinning

def main():
    try:
        print("Opening COM88...")
        port88 = serial.Serial('COM88', 115200, timeout=0.1)
        
        print("Opening COM131...")
        port131 = serial.Serial('COM131', 115200, timeout=0.1)
        
        print("Opening COM141...")
        port141 = serial.Serial('COM141', 115200, timeout=0.1)
        
        print("Starting routing...")
        print("  COM88 -> COM131 & COM141")
        print("  COM131 -> COM88")
        print("  COM141 -> COM88")
        
        # Start routing threads
        # COM88 broadcasts to both COM131 and COM141
        thread1 = threading.Thread(target=route_data, args=(port88, [port131, port141], "88->131&141"))
        
        # COM131 sends back to COM88 only
        thread2 = threading.Thread(target=route_data, args=(port131, [port88], "131->88"))
        
        # COM141 sends back to COM88 only
        thread3 = threading.Thread(target=route_data, args=(port141, [port88], "141->88"))
        
        thread1.daemon = True
        thread2.daemon = True
        thread3.daemon = True
        
        thread1.start()
        thread2.start()
        thread3.start()
        
        print("Routing active. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            port88.close()
            port131.close()
            port141.close()
        except:
            pass

if __name__ == "__main__":
    main()