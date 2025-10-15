# Serial Router Guide

## 1. Purpose

Serial Router routes serial data bidirectionally between one incoming port and two configurable outgoing ports. Data received on the incoming port is transmitted to both outgoing ports simultaneously. Data received on either outgoing port is transmitted back to the incoming port.

## 2. Prerequisites

**System Requirements:**
- Windows 10 or Windows 11
- com0com virtual serial port driver

**Port Configuration:**
- One available incoming port (physical, Moxa virtual, or other virtual port)
- Two com0com virtual port pairs configured for outgoing routing

## 3. Understanding Port Types

The application detects and categorises serial ports automatically:

**Physical Ports**: Hardware COM ports connected directly to the system.

**Moxa Virtual Ports**: Network-to-serial adapter ports. Common in marine and offshore installations where serial devices connect via network infrastructure.

**com0com Virtual Ports**: Software port pairs created by the com0com driver. Used to route serial data between applications on the same machine.

## 4. Port Pairing Fundamentals

### How com0com Port Pairs Function

com0com creates port pairs where data written to one port appears on its paired port. For example:

```
COM131 ↔ COM132 (Port Pair 1)
COM141 ↔ COM142 (Port Pair 2)
```

**Router Configuration**: The router writes outgoing data to COM131 and COM141.

**Application Configuration**: Applications read data from the paired ports COM132 and COM142.

Data flow:
```
Incoming Port → Router → COM131 → [com0com pair] → COM132 → Application 1
Incoming Port → Router → COM141 → [com0com pair] → COM142 → Application 2

Application 1 → COM132 → [com0com pair] → COM131 → Router → Incoming Port
Application 2 → COM142 → [com0com pair] → COM141 → Router → Incoming Port
```

### Critical Configuration Rule

The two outgoing ports must not be a com0com pair. Using paired ports (e.g., COM131 and COM132) as both outgoing ports creates a feedback loop where the router transmits to itself continuously. The application prevents this configuration.

## 5. com0com Driver Configuration

### Required Port Pairs

Configure two com0com port pairs. Standard configuration:
- Pair 1: COM131 ↔ COM132
- Pair 2: COM141 ↔ COM142

Port numbers may be adjusted to avoid conflicts with existing ports.

### Configuration Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| EmuBR | yes | Emulates baud rate timing behaviour |
| EmuOverrun | yes | Prevents buffer hangs by simulating hardware overflow |
| ExclusiveMode | no | Allows multiple applications to detect the port |
| AllDataBits | yes | Supports all data bit configurations (5, 6, 7, 8 bits) |
| cts | rrts | Maps Clear To Send to remote Request To Send |
| dsr | rdtr | Maps Data Set Ready to remote Data Terminal Ready |
| dcd | rdtr | Maps Data Carrier Detect to remote Data Terminal Ready |

### Setup Commands

Open the com0com Setup Command Prompt as Administrator and execute:

```cmd
install PortName=COM131,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr PortName=COM132,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr

install PortName=COM141,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr PortName=COM142,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr
```

Verify configuration in Device Manager under "Ports (COM & LPT)". All four ports should be visible.

## 6. Operation

### Starting the Application

Run `SerialRouter.exe`. The application may be minimised to the system tray whilst maintaining operation.


1. **Select Incoming Port**: Use the dropdown menu to select the source port. Physical ports and Moxa virtual ports appear in this list. com0com ports are excluded as they are reserved for outgoing routing.

2. **Select Outgoing Ports**: Configure both Outgoing Port 1 and Outgoing Port 2. These must be com0com virtual ports. Standard configuration uses COM131 and COM141.

3. **Set Baud Rate**: Select the appropriate baud rate. This rate applies to both incoming and outgoing connections. Ensure it matches the baud rate of connected devices.

4. **Start Routing**: Click "Start Routing" in the toolbar. The status indicator changes to show active routing.

### Monitoring Operation

**Status Indicators**:
- Green: Port connected and actively routing data
- Yellow: Port connecting or attempting reconnection
- Red: Port disconnected or error state

**Activity Log**: Displays connection events, data transfer milestones, and error messages.

**Data Flow Monitor**: Shows real-time byte counters and transfer rates for each routing direction.

### Stopping Operation

Click "Stop Routing" in the toolbar. The router closes all port connections and halts data transfer.

### Configuration Persistence

Click "Save Config" in the toolbar to store the current port configuration. Saved settings are automatically restored when the application restarts.

## 7. Port Selection Constraints

The application enforces the following configuration rules:

**Rule 1**: Outgoing Port 1 and Outgoing Port 2 must be different ports.

**Rule 2**: Neither outgoing port may be the same as the incoming port.

**Rule 3**: The two outgoing ports must not be a com0com pair. Adjacent port numbers (e.g., COM131 and COM132) indicate a likely pair and are rejected.

**Rule 4**: Paired ports adjacent to selected outgoing ports are excluded from incoming port selection. For example, if COM131 is selected as an outgoing port, both COM131 and COM132 are excluded from the incoming port list.

Configuration warnings appear in the Activity Log when invalid selections are attempted.

## 8. Troubleshooting

### Port Access Denied

**Symptom**: Router fails to start with "Access is denied" error.

**Cause**: Another application or router instance is using the selected port.

**Resolution**:
1. Close other applications using the port
2. Ensure no other Serial Router instance is running
3. Restart the application
4. If the error persists, restart Windows to clear port locks

### No Ports Detected

**Symptom**: Incoming port dropdown shows "(No COM ports detected)".

**Cause**: No compatible serial ports are available or port enumeration failed.

**Resolution**:
1. Verify physical ports are connected
2. Confirm com0com driver is installed (check Device Manager)
3. Click "Refresh Ports" in the toolbar
4. If using Moxa devices, verify the Moxa driver is installed

### Outgoing Ports Not Available

**Symptom**: Warning message stating required outgoing ports not found.

**Cause**: com0com port pairs are not configured.

**Resolution**:
1. Install com0com driver if not present
2. Configure required port pairs using commands in Section 5
3. Verify ports appear in Device Manager
4. Click "Refresh Ports" in the toolbar

### Configuration Warning: Paired Ports

**Symptom**: Error message when selecting outgoing ports.

**Cause**: Both outgoing ports are a com0com pair (e.g., COM131 and COM132).

**Resolution**: Select non-adjacent ports for outgoing routing. Standard configuration uses COM131 and COM141.

### Router Fails to Start

**Symptom**: "Router failed to start - check port connections" message.

**Cause**: One or more selected ports cannot be opened.

**Resolution**:
1. Verify all selected ports exist in Device Manager
2. Confirm no other application is using the ports
3. Check cable connections for physical ports
4. Review Activity Log for specific error details
5. Use "Configure Ports" toolbar button to view detailed port status

### Frequent Reconnection Events

**Symptom**: Status indicators frequently change between yellow and green.

**Cause**: Intermittent connection to incoming port.

**Resolution**:
1. Check physical cable connections
2. Verify power supply to serial devices
3. Ensure baud rate matches connected device
4. For Moxa ports, verify network connectivity

### Application Will Not Close

**Symptom**: Application window closes but process remains active.

**Resolution**:
1. Open system tray (notification area)
2. Right-click Serial Router icon
3. Select "Quit"

Alternatively, hold Shift whilst clicking the close button to quit directly without minimising to tray.

## 9. Technical Notes

### Automatic Recovery

The router automatically attempts reconnection when port connections are lost. Reconnection attempts use exponential backoff to avoid system resource exhaustion.

### Thread Management

Three independent threads handle data routing:
- One thread manages the incoming port
- Two threads manage the outgoing ports

Each thread operates independently. Failure of one thread does not affect the others.

### Data Transfer Counters

Byte counters reset automatically at 1MB intervals to prevent counter overflow during long-term operation. Session totals continue to accumulate and are displayed in routing statistics.

### System Tray Operation

The application continues routing when minimised to the system tray. Double-click the tray icon to restore the window.
