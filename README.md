<div align="center">

# SerialRouter

</div>

<div align="center">
<table>
<tr>
<td align="center">
<i>A serial port routing application designed for reliable operation in offshore environments. SerialRouter provides robust bidirectional communication between one configurable incoming port and two virtual outgoing ports with comprehensive monitoring and automatic recovery capabilities.</i>
</td>
</tr>
</table>
</div>

<br>

<div align="center">

![SerialRouter v2.0](https://img.shields.io/badge/SerialRouter-v2.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.7+-green?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)

</div>

<br>

<div align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <img width="420" alt="SerialRouter real-time monitoring dashboard displaying thread health, data transfer metrics, and operational status" src="https://github.com/user-attachments/assets/e929fbd7-9db0-49be-b433-8128fc68626e" style="border: 2px solid #ddd; border-radius: 8px;" />
        <br/>
        <sub><b>System Configuration Panel</b></sub>
        <br/>
        <sub>Automated port detection • Persistent configuration • Service deployment</sub>
      </td>
      <td align="center" width="50%">
        <img width="420" alt="SerialRouter configuration panel featuring port auto-detection and persistent settings management" src="https://github.com/user-attachments/assets/64c110e6-c20a-4967-859c-b328bc7592d2" style="border: 2px solid #ddd; border-radius: 8px;" />
        <br/>
        <sub><b>Operations Monitoring Console</b></sub>
        <br/>
        <sub>Real-time telemetry • Thread health indicators • Performance analytics</sub>
      </td>
    </tr>
  </table>
</div>

<hr style="border: none; height: 2px; background: linear-gradient(to right, #f0f0f0, #ccc, #f0f0f0);">

## Overview

<div style="background-color: #f8f9fa; padding: 20px; border-left: 4px solid #007acc; margin: 10px 0;">

SerialRouter was developed for offshore applications requiring uninterrupted serial communication routing. The system features a production-ready core engine with automatic failover, comprehensive monitoring, and a modern Qt6 GUI interface for configuration and real-time system oversight.

</div>

<hr style="border: none; height: 1px; background-color: #e1e4e8;">

## Architecture

### Core Components

<table>
<tr>
<td width="50%" style="vertical-align: top; padding-right: 20px;">

<div style="background-color: #fff5f5; padding: 15px; border: 1px solid #fed7d7; border-radius: 6px;">

**SerialRouterCore**: Routing engine:
- Three dedicated routing threads with exclusive port ownership
- Centralised PortManager preventing access conflicts
- Exponential backoff retry logic for connection failures
- Automatic thread restart with rate limiting
- Comprehensive error handling and resource management

</div>

</td>
<td width="50%" style="vertical-align: top; padding-left: 20px;">

<div style="background-color: #f0fff4; padding: 15px; border: 1px solid #c6f6d5; border-radius: 6px;">

**GUI Application**: Graphical interface:
- Real-time monitoring dashboard with live statistics
- Port configuration with auto-detection
- Activity logging with integrated backend log streaming
- Non-blocking operations using threaded architecture
- Persistent JSON-based configuration management

</div>

</td>
</tr>
</table>

### Data Flow

<div align="center" style="background-color: #f6f8fa; padding: 20px; border-radius: 8px; margin: 20px 0;">

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

</div>

<div style="background-color: #fffbf0; border: 1px solid #facc15; border-radius: 6px; padding: 15px; margin: 15px 0;">

**Configuration Steps:**
1. Select your incoming COM port from the dropdown menu
2. Configure baud rates for incoming and outgoing ports
3. Click "Start Routing" to begin operation
4. Monitor real-time statistics and system health
5. Use "Save Config" to persist your settings

</div>

### Headless Mode

<div style="background-color: #f0f0f0; padding: 15px; border-radius: 6px; border-left: 4px solid #666;">

Run the core engine directly for server deployments:
```bash
python src/core/router_engine.py
```

</div>

<hr style="border: none; height: 1px; background-color: #e1e4e8;">

## Monitoring & Logging

<div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0;">

The GUI provides detailed system monitoring:

<table style="width: 100%; margin-top: 15px;">
<tr>
<td width="50%" style="vertical-align: top; padding-right: 10px;">

- **Thread Health**: Active thread count with visual indicators
- **Data Transfer**: Live byte counters for all routing directions
- **Error Tracking**: System-wide error counts with severity indication

</td>
<td width="50%" style="vertical-align: top; padding-left: 10px;">

- **Port Status**: Connection state and ownership information
- **Performance Metrics**: Queue sizes and activity timestamps

</td>
</tr>
</table>

</div>

### Logging System

<table>
<tr>
<td width="33%" style="vertical-align: top; padding: 10px;">

<div style="background-color: #e6f3ff; padding: 12px; border-radius: 6px; text-align: center;">
<strong>File Logging</strong><br>
<small>Rotating logs stored in `serial_router.log` (10MB limit)</small>
</div>

</td>
<td width="33%" style="vertical-align: top; padding: 10px;">

<div style="background-color: #f0f8e6; padding: 12px; border-radius: 6px; text-align: center;">
<strong>Console Output</strong><br>
<small>Real-time status updates and error messages</small>
</div>

</td>
<td width="33%" style="vertical-align: top; padding: 10px;">

<div style="background-color: #fff0e6; padding: 12px; border-radius: 6px; text-align: center;">
<strong>GUI Integration</strong><br>
<small>Activity log panel with auto-scrolling</small>
</div>

</td>
</tr>
</table>

<div style="margin: 15px 0;">

- **Thread-Aware**: All log messages include originating thread names
- **Timestamped**: Precise timestamps for troubleshooting

</div>

### Status Reporting

<div style="background-color: #f6f8fa; padding: 15px; border-radius: 6px; border: 1px solid #d1d9e0;">

Access detailed system status programmatically:
```python
from src.core.router_engine import SerialRouterCore

router = SerialRouterCore()
status = router.get_status()
# Returns comprehensive dictionary with system health metrics
```

</div>

<hr style="border: none; height: 1px; background-color: #e1e4e8;">

## Production Deployment

### Reliability Features

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0;">

<div style="background-color: #f0fff4; padding: 15px; border-radius: 6px; border: 1px solid #c6f6d5;">

- **Automatic Recovery**: Connection failures handled with exponential backoff
- **Thread Monitoring**: Watchdog system restarts failed threads automatically  
- **Error Isolation**: Individual port failures don't affect system operation

</div>

<div style="background-color: #fff5f5; padding: 15px; border-radius: 6px; border: 1px solid #fed7d7;">

- **Resource Management**: Memory leak prevention for 24/7 operation
- **Graceful Shutdown**: Proper cleanup on system signals and application exit

</div>

</div>

### Offshore Considerations

<table style="width: 100%; border-collapse: collapse;">
<tr>
<td style="background-color: #f8f9fa; padding: 12px; border: 1px solid #e1e4e8; text-align: center; font-weight: bold;">Feature</td>
<td style="background-color: #f8f9fa; padding: 12px; border: 1px solid #e1e4e8; text-align: center; font-weight: bold;">Benefit</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #e1e4e8;"><strong>Minimal Complexity</strong></td>
<td style="padding: 10px; border: 1px solid #e1e4e8;">Simplified architecture reduces failure points</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #e1e4e8; background-color: #f8f9fa;"><strong>Self-Healing</strong></td>
<td style="padding: 10px; border: 1px solid #e1e4e8; background-color: #f8f9fa;">Automatic recovery from common failure modes</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #e1e4e8;"><strong>Remote Monitoring</strong></td>
<td style="padding: 10px; border: 1px solid #e1e4e8;">Comprehensive logging for remote troubleshooting</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #e1e4e8; background-color: #f8f9fa;"><strong>Configuration Flexibility</strong></td>
<td style="padding: 10px; border: 1px solid #e1e4e8; background-color: #f8f9fa;">Runtime configuration changes without restart</td>
</tr>
<tr>
<td style="padding: 10px; border: 1px solid #e1e4e8;"><strong>Signal Handling</strong></td>
<td style="padding: 10px; border: 1px solid #e1e4e8;">Responds appropriately to system shutdown signals</td>
</tr>
</table>

<hr style="border: none; height: 1px; background-color: #e1e4e8;">

## Troubleshooting

### Common Issues

<details style="background-color: #fff8f0; border: 1px solid #f0ad4e; border-radius: 6px; padding: 15px; margin: 10px 0;">
<summary style="font-weight: bold; cursor: pointer;">"Access is denied" Errors</summary>
<div style="margin-top: 10px;">

- The PortManager ensures exclusive port access - only one instance can use each port
- Close any other applications using the required COM ports
- Restart the application if ports remain locked

</div>
</details>

<details style="background-color: #f0f8ff; border: 1px solid #5bc0de; border-radius: 6px; padding: 15px; margin: 10px 0;">
<summary style="font-weight: bold; cursor: pointer;">Thread Restart Notifications</summary>
<div style="margin-top: 10px;">

- Normal operation includes automatic thread restarts for reliability
- Excessive restarts indicate hardware or driver issues
- Check serial cable connections and port availability

</div>
</details>

### Log Analysis

<div style="background-color: #f6f8fa; padding: 15px; border-radius: 6px; border-left: 4px solid #0366d6;">

Monitor `serial_router.log` for detailed operation information:
- Connection events and retry attempts
- Thread lifecycle and health status
- Data transfer statistics and error counts
- System performance metrics

</div>

<hr style="border: none; height: 1px; background-color: #e1e4e8;">

## Technical Specifications

<div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">

<table style="width: 100%; border-collapse: collapse;">
<tr>
<td style="background-color: #e6f3ff; padding: 12px; border: 1px solid #b3d9ff; font-weight: bold; width: 30%;">Component</td>
<td style="background-color: #e6f3ff; padding: 12px; border: 1px solid #b3d9ff; font-weight: bold;">Specification</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8;"><strong>Threading</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8;">Three dedicated routing threads with exclusive port ownership</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;"><strong>Concurrency</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;">Thread-safe operations using RLock and queue mechanisms</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8;"><strong>Recovery</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8;">Exponential backoff with configurable maximum delays</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;"><strong>Performance</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;">1ms polling intervals with queue-based data transfer</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8;"><strong>Monitoring</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8;">Comprehensive status API with nested health information</td>
</tr>
<tr>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;"><strong>Memory</strong></td>
<td style="padding: 12px; border: 1px solid #e1e4e8; background-color: #f8f9fa;">Automatic counter resets and queue size limits prevent memory growth</td>
</tr>
</table>

</div>

<br>

<div align="center" style="background-color: #f0f0f0; padding: 20px; border-radius: 8px; margin: 30px 0;">

<i>SerialRouter v2.0 - Production-ready serial communication routing for offshore environments</i>

</div>
