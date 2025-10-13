# SERIAL SPLITTER OPERATION GUIDE

**Document Reference:** SR-OG-001 | **Revision:** D1 | **Date:** 30 July 2025

---

*This document contains information proprietary to [YOUR COMPANY NAME] and shall not be reproduced without prior written permission.*

## REVISION LOG

| Rev. | Description |
|------|-------------|
| D1   | New Document |

---

## 1. INTRODUCTION

Serial Splitter is a production-hardened serial port routing application for offshore environments. It routes data between one incoming port and two fixed outgoing ports (COM131, COM141) with automatic recovery.

## 2. SYSTEM OVERVIEW

**Architecture:**
- 1 x Configurable incoming port → 2 x Fixed outgoing ports (COM131, COM141)
- Bidirectional communication with automatic reconnection
- Thread-safe operation with health monitoring
- Real-time GUI monitoring interface

**Requirements:**
- Windows 10/11
- Python 3.8+ with PyQt6 and pyserial
- com0com virtual serial port driver
- Available COM ports: incoming (configurable), COM131, COM141

## 3. COM0COM VIRTUAL PORT SETUP

Serial Splitter requires virtual port pairs created by com0com for proper operation.

### Required Port Pairs
- **Pair 1:** COM131 ↔ COM132
- **Pair 2:** COM141 ↔ COM142

### Configuration Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| **EmuBR** | yes | Enables baud rate emulation for realistic speed simulation |
| **EmuOverrun** | yes | Prevents buffer hangs by simulating physical port overflow behavior |
| **ExclusiveMode** | no | Keeps ports visible to all applications |
| **AllDataBits** | yes | Supports all data bit configurations (5,6,7,8 bits) |
| **cts** | rrts | Maps CTS (Clear To Send) to remote RTS signal |
| **dsr** | rdtr | Maps DSR (Data Set Ready) to remote DTR signal |
| **dcd** | rdtr | Maps DCD (Data Carrier Detect) to remote DTR signal |

### Manual Setup Commands

Open com0com Setup Command Prompt and execute:

```cmd
# Create Port Pair 1 (COM131/COM132)
command> install PortName=COM131,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr PortName=COM132,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr

# Create Port Pair 2 (COM141/COM142)  
command> install PortName=COM141,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr PortName=COM142,EmuBR=yes,EmuOverrun=yes,ExclusiveMode=no,AllDataBits=yes,cts=rrts,dsr=rdtr,dcd=rdtr
```

## 4. INSTALLATION

1. Install com0com virtual serial port driver
2. Configure virtual port pairs (see Section 3)
3. Extract Serial Splitter files to installation directory
4. Install dependencies: `pip install PyQt6 pyserial`
5. Verify installation: `python main.py`

## 5. OPERATION

### Starting the System
```bash
# GUI Mode (Recommended)
python main.py

# Headless Mode
python src/core/router_engine.py
```

### Configuration
Edit `config/serial_router_config.json`:
```json
{
  "incoming_port": "COM54",
  "incoming_baud": 115200,
  "outgoing_baud": 115200,
  "timeout": 0.1,
  "retry_delay_max": 30,
  "log_level": "INFO"
}
```

### Normal Operation
1. Launch application: `python main.py`
2. Select incoming port from dropdown
3. Click "Start" to begin routing
4. Monitor status indicators:
   - **Green:** Connected and active
   - **Yellow:** Connecting/reconnecting  
   - **Red:** Disconnected/error

## 6. MONITORING

**Real-time Status:**
- Connection indicators for all ports
- Data transfer counters
- Connection uptime
- Error statistics

**Logging:**
- File: `serial_router.log` (10MB rotation)
- Levels: INFO, WARNING, ERROR, DEBUG

## 7. TROUBLESHOOTING

### Common Issues

**Application Won't Start:**
- Install dependencies: `pip install PyQt6 pyserial`
- Run as administrator
- Check Python version (3.8+)

**COM Port Access Denied:**
- Close other applications using ports
- Check Device Manager for conflicts
- Restart system to clear port locks

**Virtual Ports Missing:**
- Verify com0com installation
- Check port pair configuration
- Reinstall virtual port pairs if needed

**No Data Transfer:**
- Verify baud rate settings match devices
- Check cable connections
- Confirm COM131/COM141 availability

**Frequent Disconnections:**
- Check cable connections
- Verify power supply stability
- Adjust timeout in configuration

### Restart Procedures

**Software Restart:**
1. Close and relaunch application
2. Restart Windows (if unresponsive)
3. Hard reset (last resort)

**After Power Loss:**
- System auto-starts if configured
- Manual start: Double-click desktop icon or run `python main.py`

## 8. CONTACT INFORMATION

| Role | Contact |
|------|---------|
| Technical Support | [TO BE COMPLETED] |
| System Administrator | [TO BE COMPLETED] |

---

**For technical support, contact designated personnel listed above.**