# SerialRouter

A serial port routing application designed for reliable operation in offshore environments. SerialRouter provides robust bidirectional communication between one configurable incoming port and two virtual outgoing ports with comprehensive monitoring and automatic recovery capabilities.


![SerialRouter v2.0](https://img.shields.io/badge/SerialRouter-v2.0-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)

<img width="871" height="624" alt="port_router_screen" src="https://github.com/user-attachments/assets/0b135ea0-80ca-4367-8a1b-784c8f468de9" />

## Overview

SerialRouter was developed for offshore applications requiring uninterrupted serial communication routing. The system features a production-ready core engine with automatic failover, comprehensive monitoring, and a modern Qt6 GUI interface for configuration and real-time system oversight.

## Architecture

### Core Components

**SerialRouterCore**: Routing engine:
- Three dedicated routing threads with exclusive port ownership
- Centralised PortManager preventing access conflicts
- Exponential backoff retry logic for connection failures
- Automatic thread restart with rate limiting
- Comprehensive error handling and resource management

**GUI Application**: Graphical interface:
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
## Monitoring & Logging

The GUI provides detailed system monitoring:

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



*SerialRouter v2.0 - Production-ready serial communication routing for offshore environments*
