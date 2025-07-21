# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SerialRouter is a production-hardened Python application for routing serial port communications in offshore environments. The system routes data between an incoming port and two fixed outgoing ports (COM131, COM141) with bidirectional communication and automatic recovery capabilities.

## Core Architecture

### Entry Points
- `main.py` - GUI entry point that launches the PyQt6 interface
- `src/core/router_engine.py` - Core routing engine (can be run standalone)
- `src/gui/main_window.py` - Complete GUI application

### Key Components

**SerialRouterCore** (`src/core/router_engine.py`):
- Production-hardened routing engine with thread-safe operation
- Uses centralized PortManager for exclusive port ownership
- Three routing threads: IncomingPortOwner, Port131Owner, Port141Owner  
- Built-in watchdog monitoring with automatic thread restart
- Exponential backoff retry logic for connection failures

**PortManager** (`src/core/router_engine.py:29-311`):
- Thread-safe serial port connection manager
- Prevents "Access is denied" errors through exclusive ownership
- Data queuing system for cross-thread communication
- Comprehensive port health monitoring and statistics

**GUI Application** (`src/gui/main_window.py`):
- PyQt6-based interface with real-time monitoring
- Non-blocking operations using QThread wrapper
- JSON configuration persistence
- Integrated logging display

## Configuration

Configuration is managed via `config/serial_router_config.json`:
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

**Fixed Architecture**: The system always routes to COM131 and COM141 as outgoing ports. Only the incoming port is configurable.

## Common Commands

### Running the Application
```bash
# GUI mode (recommended)
python main.py

# Direct core engine (headless)
python src/core/router_engine.py
```

### Testing
```bash
# Integration test (validates core functionality without GUI)
python tests/test_gui_integration.py
```

### Dependencies
The project requires:
- PyQt6 (for GUI)
- pyserial (for serial communication)
- Standard library modules (threading, logging, json, etc.)

## Development Notes

### Thread Architecture
- Three dedicated threads for port handling with exclusive ownership
- Thread health monitoring with automatic restart on failure
- Rate-limited thread restarts (max 10 per hour per thread)
- Watchdog monitor runs every 10 seconds

### Port Management
- Centralized PortManager prevents port access conflicts
- Each thread owns one port exclusively during operation
- Data flows through queues between threads
- Automatic reconnection with exponential backoff

### Error Handling
- Graceful degradation with continued operation despite individual port failures
- Comprehensive logging to `serial_router.log` with rotation (10MB files)
- Connection retry logic with configurable maximum delays
- Memory leak prevention for long-term operation

### GUI Integration
- Non-blocking start/stop operations using RouterControlThread
- Real-time status updates every 1 second
- Custom log handler bridges core engine logging to GUI display
- Configuration persistence with JSON validation

## File Structure
```
SerialRouter/
├── main.py                     # GUI entry point
├── config/
│   └── serial_router_config.json  # Runtime configuration
├── src/
│   ├── core/
│   │   └── router_engine.py    # Core routing engine
│   └── gui/
│       └── main_window.py      # PyQt6 GUI application
└── tests/
    └── test_gui_integration.py # Backend integration tests
```