# Utils Changelog

## [Unreleased]
### Changed
- Consolidated header normalization logic into `normalization.py`
- Removed duplicate normalization code from `data_cleaner.py`
- Improved type hints and documentation in normalization functions
- Enhanced error handling in data cleaning operations

### Added
- New data cleaning utilities for PII handling
- Enhanced string normalization functions
- Improved error tracking in utility functions

### Removed
- Removed redundant header normalization code from `data_cleaner.py`
- Removed duplicate header mapping functionality

## [2024-03-19] - Header Normalization Consolidation
### Added
- New `normalize_header` function with comprehensive header normalization
- Added fuzzy matching support for header mapping
- Added type hints and improved documentation

### Changed
- Moved all header normalization logic to `normalization.py`
- Updated `DataCleaner` to use consolidated normalization functions
- Improved error handling in normalization functions

### Removed
- Removed duplicate normalization code from multiple files
- Removed redundant header mapping functionality

## [2024-03-18] - Initial Setup
### Added
- Basic utility functions for data cleaning and validation
- Error handling utilities
- Logging setup
- Data normalization functions 