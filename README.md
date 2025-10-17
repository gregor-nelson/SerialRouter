# Serial Router

A virtual serial port routing application. Provides bidirectional communication between one configurable incoming port and two virtual outgoing ports with comprehensive monitoring and automatic recovery capabilities.


## Architecture

### Components

**Core**:
- Three dedicated routing threads with exclusive port ownership
- Centralised PortManager preventing access conflicts
- Exponential backoff retry logic for connection failures
- Automatic thread restart with rate limiting
- Comprehensive error handling and resource management

**GUI**: 
- Real-time monitoring dashboard with live statistics
- Port configuration with auto-detection
- Activity logging with integrated backend log streaming
- Non-blocking operations using threaded architecture
- Persistent JSON-based configuration management

### Headless

Run the core engine directly for server deployments:
```bash
python src/core/router_engine.py
```
## Monitoring

- **Thread Health**: Active thread count with visual indicators
- **Data Transfer**: Live byte counters for all routing directions
- **Error Tracking**: System-wide error counts with severity indication
- **Port Status**: Connection state and ownership information
- **Performance Metrics**: Queue sizes and activity timestamps

### Logging

- **File Logging**: Rotating logs stored in `serial_router.log` (10MB limit)
- **Console Output**: Real-time status updates and error messages
- **GUI Integration**: Activity log panel with auto-scrolling
- **Thread-Aware**: All log messages include originating thread names
- **Timestamped**: Precise timestamps for troubleshooting

## Technical

- **Threading**: Three dedicated routing threads with exclusive port ownership
- **Concurrency**: Thread-safe operations using RLock and queue mechanisms
- **Recovery**: Exponential backoff with configurable maximum delays
- **Performance**: 1ms polling intervals with queue-based data transfer
- **Monitoring**: Comprehensive status API with nested health information
- **Memory**: Automatic counter resets and queue size limits prevent memory growth

*Serial Router v1.0.2 
