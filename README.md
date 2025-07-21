# SerialRouter

A production-hardened serial port routing application designed for reliable operation in offshore environments. SerialRouter provides robust bidirectional communication between one configurable incoming port and two fixed outgoing ports (COM131, COM141) with comprehensive monitoring and automatic recovery capabilities.

![SerialRouter v2.0](https://img.shields.io/badge/SerialRouter-v2.0-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)
![License](https://img.shields.io/badge/License-Proprietary-red)

## Overview

SerialRouter was developed for critical offshore applications requiring uninterrupted serial communication routing. The system features a production-ready core engine with automatic failover, comprehensive monitoring, and an intuitive PyQt6 GUI interface for configuration and real-time system oversight.

### Key Features

- **Production-Grade Reliability**: Thread-safe operation with automatic recovery and watchdog monitoring
- **Fixed Routing Architecture**: One incoming port distributes to COM131 and COM141, with full bidirectional communication
- **Real-Time Monitoring**: Live data transfer statistics, thread health monitoring, and error tracking
- **Intuitive GUI**: Professional PyQt6 interface with configuration management and activity logging
- **Offshore Ready**: Designed for unmanned, long-term operation in challenging environments

## Architecture

### Core Components

**SerialRouterCore**: Production-hardened routing engine featuring:
- Three dedicated routing threads with exclusive port ownership
- Centralised PortManager preventing access conflicts
- Exponential backoff retry logic for connection failures
- Automatic thread restart with rate limiting
- Comprehensive error handling and resource management

**GUI Application**: Professional interface providing:
- Real-time monitoring dashboard with live statistics
- Port configuration with auto-detection
- Activity logging with integrated backend log streaming
- Non-blocking operations using threaded architecture
- Persistent JSON-based configuration management

### Data Flow

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│ Incoming    │◄──►│   SerialRouter   │◄──►│   COM131    │
│ Port (Conf) │    │   Core Engine    │    │   (Fixed)   │
└─────────────┘    │                  │    └─────────────┘
                   │                  │    ┌─────────────┐
                   │                  │◄──►│   COM141    │
                   └──────────────────┘    │   (Fixed)   │
                                           └─────────────┘
```

## Installation

### Prerequisites

- Python 3.7 or later
- PyQt6 (for GUI operation)
- pyserial (for serial communication)

### Setup

1. **Clone or extract the project files**
2. **Install required dependencies:**
   ```bash
   pip install PyQt6 pyserial
   ```
3. **Ensure the directory structure is intact:**
   ```
   SerialRouter/
   ├── main.py
   ├── config/
   │   └── serial_router_config.json
   ├── src/
   │   ├── core/
   │   │   └── router_engine.py
   │   └── gui/
   │       └── main_window.py
   └── tests/
       └── test_gui_integration.py
   ```

## Usage

### GUI Mode (Recommended)

Launch the graphical interface:
```bash
python main.py
```

**Configuration Steps:**
1. Select your incoming COM port from the dropdown menu
2. Configure baud rates for incoming and outgoing ports
3. Click "Start Routing" to begin operation
4. Monitor real-time statistics and system health
5. Use "Save Config" to persist your settings

### Headless Mode

Run the core engine directly for server deployments:
```bash
python src/core/router_engine.py
```

### Testing

Validate the installation and integration:
```bash
python tests/test_gui_integration.py
```

## Configuration

Settings are managed through `config/serial_router_config.json`:

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

### Configuration Options

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `incoming_port` | Configurable COM port | "COM54" | Any available COM port |
| `incoming_baud` | Incoming port baud rate | 115200 | 1200-921600 |
| `outgoing_baud` | Outgoing ports baud rate | 115200 | 1200-921600 |
| `timeout` | Serial port timeout (seconds) | 0.1 | 0.001-10.0 |
| `retry_delay_max` | Maximum retry delay (seconds) | 30 | 1-300 |
| `log_level` | Logging verbosity | "INFO" | DEBUG, INFO, WARNING, ERROR |

## Monitoring & Logging

### Real-Time Monitoring

The GUI provides comprehensive system monitoring:

- **Thread Health**: Active thread count with visual indicators
- **Data Transfer**: Live byte counters for all routing directions
- **Error Tracking**: System-wide error counts with severity indication
- **Port Status**: Connection state and ownership information
- **Performance Metrics**: Queue sizes and activity timestamps

### Logging System

- **File Logging**: Rotating logs stored in `serial_router.log` (10MB limit)
- **Console Output**: Real-time status updates and error messages
- **GUI Integration**: Activity log panel with auto-scrolling
- **Thread-Aware**: All log messages include originating thread names
- **Timestamped**: Precise timestamps for troubleshooting

### Status Reporting

Access detailed system status programmatically:
```python
from src.core.router_engine import SerialRouterCore

router = SerialRouterCore()
status = router.get_status()
# Returns comprehensive dictionary with system health metrics
```

## Production Deployment

### Reliability Features

- **Automatic Recovery**: Connection failures handled with exponential backoff
- **Thread Monitoring**: Watchdog system restarts failed threads automatically  
- **Error Isolation**: Individual port failures don't affect system operation
- **Resource Management**: Memory leak prevention for 24/7 operation
- **Graceful Shutdown**: Proper cleanup on system signals and application exit

### Offshore Considerations

- **Minimal Complexity**: Simplified architecture reduces failure points
- **Self-Healing**: Automatic recovery from common failure modes
- **Remote Monitoring**: Comprehensive logging for remote troubleshooting
- **Configuration Flexibility**: Runtime configuration changes without restart
- **Signal Handling**: Responds appropriately to system shutdown signals

## Troubleshooting

### Common Issues

**"Access is denied" Errors**
- The PortManager ensures exclusive port access - only one instance can use each port
- Close any other applications using the required COM ports
- Restart the application if ports remain locked

**Thread Restart Notifications**
- Normal operation includes automatic thread restarts for reliability
- Excessive restarts indicate hardware or driver issues
- Check serial cable connections and port availability

**Configuration Not Saving**
- Ensure the `config/` directory exists and is writable
- Check file permissions on `serial_router_config.json`
- Verify JSON syntax if editing configuration manually

### Log Analysis

Monitor `serial_router.log` for detailed operation information:
- Connection events and retry attempts
- Thread lifecycle and health status
- Data transfer statistics and error counts
- System performance metrics

## Technical Specifications

- **Threading**: Three dedicated routing threads with exclusive port ownership
- **Concurrency**: Thread-safe operations using RLock and queue mechanisms
- **Recovery**: Exponential backoff with configurable maximum delays
- **Performance**: 1ms polling intervals with queue-based data transfer
- **Monitoring**: Comprehensive status API with nested health information
- **Memory**: Automatic counter resets and queue size limits prevent memory growth

## Support

For technical support or deployment assistance:
- Review the activity logs for detailed error information
- Check thread health and port connection status in the GUI
- Validate configuration settings and port availability
- Ensure proper serial cable connections and port permissions

---

*SerialRouter v2.0 - Production-ready serial communication routing for offshore environments*