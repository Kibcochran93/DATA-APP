# Data Validation and Protection Application

A robust application for data validation, cleaning, and protection with comprehensive error handling and security features.

## Features

- Data validation and cleaning
- PII detection and masking
- Secure file processing
- User authentication and authorization
- Error tracking and monitoring
- Comprehensive logging

## Error Handling System

The application implements a sophisticated error handling system that provides:

- Consistent error management across components
- Detailed error logging and tracking
- User-friendly error messages
- Security event monitoring
- Error pattern analysis

### Key Components

1. **Error Classes**
   - `BaseError`: Foundation for all application errors
   - `ValidationError`: Data validation failures
   - `DataError`: Data processing issues
   - `SecurityError`: Security-related problems
   - `AuthenticationError`: Authentication failures
   - `AuthorizationError`: Authorization issues

2. **Error Handling Functions**
   - `handle_error`: Central error handling
   - `track_error`: Error tracking
   - `setup_error_logging`: Logging configuration

3. **Integration Points**
   - Data cleaning operations
   - File processing
   - User authentication
   - Data validation
   - Security monitoring

## Project Structure

```
.
├── app.py                 # Main application
├── config.py             # Configuration
├── docs/                 # Documentation
│   └── error_handling.md # Error handling docs
├── security/            # Security components
├── utils/              # Utility modules
│   ├── data_cleaner.py # Data cleaning
│   ├── error_handler.py # Error handling
│   └── logger.py       # Logging
└── tests/              # Test suite
```

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

## Building the Executable

### Prerequisites
- Python 3.8 or higher
- Windows operating system
- All dependencies installed

### Build Steps

1. Install build dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the build script:
   ```bash
   python build.py
   ```

3. The executable will be created in the `dist` directory:
   - `dist/DataValidationApp.exe`

### Running the Executable

1. Navigate to the `dist` directory
2. Double-click `DataValidationApp.exe` or run from command line:
   ```bash
   DataValidationApp.exe
   ```

### Build Configuration

The build process:
- Packages all necessary files and dependencies
- Includes configuration files
- Bundles documentation
- Creates a single executable

### Troubleshooting Build Issues

1. **Missing Dependencies**
   - Ensure all requirements are installed
   - Check for any missing Python packages
   - Verify Python version compatibility

2. **File Access Issues**
   - Run as administrator if needed
   - Check file permissions
   - Ensure no files are in use

3. **Build Errors**
   - Check the build log
   - Verify file paths
   - Ensure all required files exist

## Error Handling Best Practices

1. **Error Creation**
   - Use appropriate error classes
   - Provide clear messages
   - Include relevant context
   - Preserve original errors

2. **Error Handling**
   - Use centralized handling
   - Provide operation context
   - Consider user feedback
   - Track errors appropriately

3. **Logging**
   - Use appropriate levels
   - Include full context
   - Preserve stack traces
   - Monitor patterns

## Security Features

- Input validation
- Data sanitization
- PII protection
- Access control
- Security monitoring
- Audit logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Documentation

- [Error Handling System](docs/error_handling.md)
- [Security Features](docs/security.md)
- [API Documentation](docs/api.md)
- [User Guide](docs/user_guide.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 